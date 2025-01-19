from setuptools import setup, find_packages

setup(
    name="kithara",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "flax>=0.7.0",
        "datasets>=3.0.1",
        "huggingface-hub>=0.25.1",
        "jax>=0.4.38",
        "keras>=3.8.0",
        "transformers>=4.45.1",
        "keras-nlp==0.18.1",
        "google-api-python-client>=2.159.0",
        "google-auth-httplib2>=0.2.0",
        "google-auth-oauthlib>=1.2.1",
        "ray[default]>=2.40.0",
        "torch>=2.5.1",
        "peft>=0.14.0",
        "hf_transfer>=0.1.9"
    ],
)
