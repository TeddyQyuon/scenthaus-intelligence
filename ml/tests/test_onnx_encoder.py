import numpy as np

from ml.embeddings import mean_pool


def test_onnx_mean_pool_ignores_padding_and_normalizes():
    hidden = np.array(
        [[[1.0, 0.0], [0.0, 2.0], [0.0, 100.0]]], dtype=np.float32
    )
    mask = np.array([[1, 1, 0]], dtype=np.int64)

    result = mean_pool(hidden, mask)

    np.testing.assert_allclose(result, [[1 / np.sqrt(5), 2 / np.sqrt(5)]])
    np.testing.assert_allclose(np.linalg.norm(result, axis=1), [1.0])
