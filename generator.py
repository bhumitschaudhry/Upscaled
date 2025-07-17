import torch
import torch.nn as nn
class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, 3, 1, 1),
            nn.BatchNorm2d(channels),
            nn.PReLU(),
            nn.Conv2d(channels, channels, 3, 1, 1),
            nn.BatchNorm2d(channels)
        )
    def forward(self, x):
        return x + self.block(x)
class Generator(nn.Module):
    def __init__(self, scale_factor = 4, num_residuals = 16):
        super().__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(3, 64, 9, 1, 4),
            nn.PReLU()
        )
        self.residual_blocks = nn.Sequential(
            *[ResidualBlock(64) for _ in range(num_residuals)]
        )
        self.block2 = nn.Sequential(
            nn.Conv2d(64, 64, 3, 1, 1),
            nn.BatchNorm2d(64)
        )
        upsample_layers = []
        for _ in range(int(scale_factor / 2)):
            upsample_layers += [
                nn.Conv2d(64, 256, 3, 1, 1),
                nn.PixelShuffle(2),
                nn.PReLU()
            ]
        self.upsample = nn.Sequential(*upsample_layers)
        self.block3 = nn.Conv2d(64, 3, 9, 1, 4)
    def forward(self, x):
        x1 = self.block1(x)
        x2 = self.residual_blocks(x1)
        x3 = self.block2(x2)
        x = x1 + x3
        x = self.upsample(x)
        return self.block3(x)
