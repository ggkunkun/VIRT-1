"""Virtu-Omni-10B: Universal Multimodal Foundation Model.

Industrial-grade implementation of a fully proprietary end-to-end multimodal
architecture supporting unified representation space, bidirectional cross-modal
interaction (text-to-image and image-to-text), 3D parallelism topology, and
high-reliability operational infrastructure.
"""

__version__ = "1.0.0"
__author__ = "Virtu Multimodal Architecture Team"
__all__ = [
    "VirtuOmniConfig",
    "VirtuOmni10B",
    "BaseParameterExpander",
    "AlignmentValidator",
    "StreamingMultimodalDataPipeline",
    "Distributed3DTrainer",
    "TrainingHealthMonitor",
]

from virtu_omni.config import VirtuOmniConfig
from virtu_omni.models.architecture import VirtuOmni10B
from virtu_omni.models.expander import BaseParameterExpander
from virtu_omni.alignment.aligner import AlignmentValidator
from virtu_omni.data.pipeline import StreamingMultimodalDataPipeline
from virtu_omni.training.trainer import Distributed3DTrainer
from virtu_omni.training.monitor import TrainingHealthMonitor
