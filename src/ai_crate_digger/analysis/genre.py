"""Genre classification using Essentia."""

import json
import logging
import urllib.request
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Model paths
MODEL_DIR = Path.home() / ".ai-crate-digger" / "models"
MODEL_URL = "https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.pb"
MODEL_PATH = MODEL_DIR / "discogs-effnet-bs64-1.pb"
LABELS_URL = "https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.json"
LABELS_PATH = MODEL_DIR / "discogs-effnet-bs64-1.json"

# Lazy-loaded globals
_model = None
_labels: list[str] = []
_tf_available: bool | None = None  # None = not yet checked


def _check_tf_available() -> bool:
    """Check once whether essentia-tensorflow is installed."""
    global _tf_available
    if _tf_available is None:
        try:
            from essentia.standard import TensorflowPredictEffnetDiscogs  # noqa: F401

            _tf_available = True
        except ImportError:
            _tf_available = False
            logger.debug(
                "essentia-tensorflow not installed -- genre classification disabled. "
                "Install with: pip install essentia-tensorflow"
            )
    return _tf_available


def _ensure_model_downloaded() -> None:
    """Download model if not present."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not MODEL_PATH.exists():
        logger.info("Downloading Essentia genre model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        logger.info("Model downloaded to %s", MODEL_PATH)

    if not LABELS_PATH.exists():
        logger.info("Downloading genre labels...")
        urllib.request.urlretrieve(LABELS_URL, LABELS_PATH)
        logger.info("Labels downloaded to %s", LABELS_PATH)


def _load_model() -> None:
    """Load the Essentia model (lazy loading)."""
    global _model, _labels

    if _model is not None:
        return

    _ensure_model_downloaded()

    # Load labels
    with open(LABELS_PATH) as f:
        metadata = json.load(f)
        _labels = metadata["classes"]

    # Import here to avoid slow import at module level
    from essentia.standard import TensorflowPredictEffnetDiscogs

    _model = TensorflowPredictEffnetDiscogs(graphFilename=str(MODEL_PATH))
    logger.info("Essentia genre model loaded with %d labels", len(_labels))


def classify_genre(
    file_path: Path,
    top_n: int = 3,
    min_confidence: float = 0.15,
) -> list[str]:
    """Classify genre of an audio file using Essentia.

    Args:
        file_path: Path to audio file
        top_n: Maximum number of genres to return
        min_confidence: Minimum confidence threshold (0-1)

    Returns:
        List of genre strings (simplified, without "Electronic---" prefix)
    """
    if not _check_tf_available():
        return []

    try:
        _load_model()
        from essentia.standard import MonoLoader

        # Load audio at 16kHz (required by model)
        audio = MonoLoader(filename=str(file_path), sampleRate=16000)()

        # Run prediction
        assert _model is not None, "Model should be loaded"
        predictions = _model(audio)

        # Average predictions across time frames
        avg_predictions = np.mean(predictions, axis=0)

        # Get top genres above threshold
        genres = []
        top_indices = np.argsort(avg_predictions)[-top_n:][::-1]

        for idx in top_indices:
            confidence = avg_predictions[idx]
            if confidence >= min_confidence:
                # Simplify label: "Electronic---House" -> "House"
                label = _labels[idx]
                if "---" in label:
                    label = label.split("---")[-1]
                genres.append(label)

        return genres

    except Exception as e:
        logger.warning("Genre classification failed for %s: %s", file_path, e)
        return []


def extract_folder_hint(file_path: Path) -> list[str]:
    """Extract folder name as genre hints (normalized).

    Args:
        file_path: Path to audio file

    Returns:
        List of normalized tags from folder name, empty if not useful
    """
    import re

    folder_name = file_path.parent.name

    # Skip if it looks like a year or date folder
    if folder_name.isdigit():
        return []
    if folder_name.startswith("20") and len(folder_name) == 4:
        return []

    # Skip common non-genre folder names
    skip_folders = {
        "music",
        "mp3",
        "downloads",
        "new",
        "unsorted",
        "misc",
        "various",
        "compilations",
        "singles",
        "albums",
        "tracks",
    }
    if folder_name.lower() in skip_folders:
        return []

    # Skip if it's a path-like name (contains artist names with separators)
    if " - " in folder_name and len(folder_name) > 50:
        return []

    # Normalize: split by delimiters, clean up
    results = []
    parts = re.split(r"\s*/\s*|\s*:\s*", folder_name)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Remove trailing numbers
        part = re.sub(r"\s+\d+$", "", part)
        # Remove year patterns
        part = re.sub(r"\s+20\d{2}\b", "", part)
        # Remove noise words
        part = re.sub(r"\s+(andre|batz|mp3|folder)$", "", part, flags=re.IGNORECASE)

        part = part.strip()

        # Skip if too short, just numbers, or noise
        if len(part) < 2 or part.isdigit():
            continue
        if part.lower() in skip_folders:
            continue

        results.append(part)

    return results
