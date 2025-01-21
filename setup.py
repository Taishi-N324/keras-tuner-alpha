from setuptools import setup, find_packages

setup(
    name="kithara",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "flax>=0.7.0",
        "datasets",
        "huggingface-hub",
        "jax>=0.4.30",
        "jaxlib>=0.4.30",
        "keras>=3.8.0",
        "transformers>=4.45.1",
        "keras-nlp>=0.18.1",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "ray[default]",
        "torch",
        "peft",
        "hf_transfer",
        # MaxText dependencies
        "aqtp",
        "grain-nightly",
        "orbax-checkpoint",
        "google-cloud-logging",
        "tensorboardx",
        "ml-collections",
        "tensorflow_datasets",
        "sentencepiece",
        "tiktoken",
        "pathwaysutils@git+https://github.com/google/pathways-utils.git",
        "cloud-accelerator-diagnostics",
        "cloud-tpu-diagnostics",
        "ml-goodput-measurement"
    ],
)
