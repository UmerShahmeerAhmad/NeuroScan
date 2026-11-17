"""
MS-CBAM-Net (residual) and its out-of-distribution (OOD) scorer.

The layer classes below are copied from the training notebook without any
change to names, shapes or ordering, because the saved weights must match them
key for key. Do not rename layers here.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

ARCH_TAG = "mscbam"  # what MODEL_ARCH / the checkpoint's "architecture" field is matched against


class MultiScaleBlock(nn.Module):
    """Three parallel conv branches (3x3, 5x5, dilated 3x3) fused via 1x1 conv."""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        ch_a = out_ch // 3
        ch_b = out_ch // 3
        ch_c = out_ch - ch_a - ch_b

        self.branch_a = nn.Sequential(
            nn.Conv2d(in_ch, ch_a, kernel_size=3, padding=1),
            nn.BatchNorm2d(ch_a),
            nn.ReLU(inplace=True),
        )
        self.branch_b = nn.Sequential(
            nn.Conv2d(in_ch, ch_b, kernel_size=5, padding=2),
            nn.BatchNorm2d(ch_b),
            nn.ReLU(inplace=True),
        )
        self.branch_c = nn.Sequential(
            nn.Conv2d(in_ch, ch_c, kernel_size=3, padding=2, dilation=2),
            nn.BatchNorm2d(ch_c),
            nn.ReLU(inplace=True),
        )
        self.fuse = nn.Sequential(
            nn.Conv2d(out_ch, out_ch, kernel_size=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        a = self.branch_a(x)
        b = self.branch_b(x)
        c = self.branch_c(x)
        return self.fuse(torch.cat([a, b, c], dim=1))


class CBAM(nn.Module):
    """Channel attention followed by spatial attention."""

    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)

        hidden = max(channels // reduction, 1)
        self.shared_mlp = nn.Sequential(
            nn.Linear(channels, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, channels),
        )
        self.sigmoid_channel = nn.Sigmoid()

        self.spatial_conv = nn.Conv2d(2, 1, kernel_size=7, padding=3)
        self.sigmoid_spatial = nn.Sigmoid()

    def forward(self, x):
        b, c, _h, _w = x.shape

        avg_out = self.shared_mlp(self.avg_pool(x).view(b, c))
        max_out = self.shared_mlp(self.max_pool(x).view(b, c))
        channel_att = self.sigmoid_channel(avg_out + max_out).view(b, c, 1, 1)
        x = x * channel_att

        avg_map = torch.mean(x, dim=1, keepdim=True)
        max_map, _ = torch.max(x, dim=1, keepdim=True)
        spatial_in = torch.cat([avg_map, max_map], dim=1)
        spatial_att = self.sigmoid_spatial(self.spatial_conv(spatial_in))
        return x * spatial_att


class ResidualMSCBAMStage(nn.Module):
    """MultiScaleBlock then CBAM, with an identity or 1x1-projection shortcut."""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.ms_block = MultiScaleBlock(in_ch, out_ch)
        self.cbam = CBAM(out_ch)
        if in_ch != out_ch:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, kernel_size=1),
                nn.BatchNorm2d(out_ch),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x):
        identity = self.shortcut(x)
        out = self.ms_block(x)
        out = self.cbam(out)
        out = out + identity
        return F.relu(out, inplace=True)


class ResidualDownsample(nn.Module):
    """Stride-2 residual block (ResNet-style)."""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv1 = nn.Conv2d(in_ch, out_ch, kernel_size=3, stride=2, padding=1)
        self.bn1 = nn.BatchNorm2d(out_ch)
        self.conv2 = nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.shortcut = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=1, stride=2),
            nn.BatchNorm2d(out_ch),
        )

    def forward(self, x):
        identity = self.shortcut(x)
        out = F.relu(self.bn1(self.conv1(x)), inplace=True)
        out = self.bn2(self.conv2(out))
        out = out + identity
        return F.relu(out, inplace=True)


class MSCBAMNetSGM(nn.Module):
    """MS-CBAM-Net. forward() returns (logits, pooled_512_dim_features)."""

    OUTPUT_DIM = 512

    def __init__(self, num_classes):
        super().__init__()

        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

        self.stage1 = ResidualMSCBAMStage(64, 64)
        self.down1 = ResidualDownsample(64, 64)

        self.stage2 = ResidualMSCBAMStage(64, 128)
        self.down2 = ResidualDownsample(128, 128)

        self.stage3 = ResidualMSCBAMStage(128, 256)
        self.down3 = ResidualDownsample(256, 256)

        self.stage4 = ResidualMSCBAMStage(256, 512)

        # `features` re-uses the modules above, so the saved weights hold both
        # "stage1.*" and "features.1.*" keys. This is expected.
        self.features = nn.Sequential(
            self.stem,
            self.stage1, self.down1,
            self.stage2, self.down2,
            self.stage3, self.down3,
            self.stage4,
        )

        self.global_pool = nn.AdaptiveAvgPool2d(1)

        self.classifier = nn.Sequential(
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.25),
            nn.Linear(256, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.15),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        feat_map = self.features(x)
        pooled = self.global_pool(feat_map).flatten(1)
        logits = self.classifier(pooled)
        return logits, pooled


class MahalanobisOOD:
    """Feature-space distance check, rebuilt from the numbers saved in the checkpoint.

    The notebook measures, for every real tumor class, the Mahalanobis distance
    between an image's 512-number feature vector and that class's average
    feature vector (one covariance shared by all classes), and keeps the smallest.
    An image farther than the saved threshold does not look like the training MRIs.
    """

    def __init__(self, mu_c: dict, sigma_inv, threshold: float):
        # mu_c: {class_index: list or tensor of 512 numbers}; sigma_inv: 512x512 nested list or tensor
        keys = sorted(int(k) for k in mu_c)
        self.class_indices = keys
        self.mu = torch.stack([torch.as_tensor(mu_c[k] if k in mu_c else mu_c[str(k)], dtype=torch.float32)
                               for k in keys])                       # (n_classes, 512)
        self.sigma_inv = torch.as_tensor(sigma_inv, dtype=torch.float32)  # (512, 512)
        self.threshold = float(threshold)
        if self.mu.shape[1] != self.sigma_inv.shape[0] or self.sigma_inv.shape[0] != self.sigma_inv.shape[1]:
            raise ValueError(
                f"Mahalanobis data has inconsistent shapes: mu {tuple(self.mu.shape)}, "
                f"sigma_inv {tuple(self.sigma_inv.shape)}."
            )

    def distance(self, pooled: torch.Tensor) -> torch.Tensor:
        """pooled: (B, 512) on the CPU. Returns the (B,) smallest distance to any class."""
        diff = pooled.unsqueeze(1) - self.mu.unsqueeze(0)               # (B, C, 512)
        m = torch.einsum("bci,ij,bcj->bc", diff, self.sigma_inv, diff)  # (B, C)
        return torch.sqrt(torch.clamp(m, min=0.0)).min(dim=1).values
