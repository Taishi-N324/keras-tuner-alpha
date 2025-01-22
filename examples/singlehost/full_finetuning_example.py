"""Full parameter finetune a Gemma2 9B model.

This script demonstrates how to:
1. Set up a Gemma2 model for full parameter finetuning
2. Load HuggingFace Gemma2 checkpoint
3. Configure data loading and preprocessing
4. Run training across TPU/GPU devices
5. Save checkpoint to GCS periodically 
6. Generate text using the trained model
7. Save model in HuggingFace format to GCS

This script should be run on multihost, since gemma2-9b will not fit on a single host. However, 
you can change the model to `gemma2-2b` to run on single host. 

Singlehost: python examples/singlehost/full_finetuning_example.py 
Multihost:  python ray/submit_job.py "python3 examples/multihost/ray/TPU/full_finetuning_example.py" --hf-token <TOKEN>

If you experience OOM error during model checkpoint loading/saving, it is because your host VM does not have enough 
capacity to load/save the model. Consider mounting extra memory onto your VM, and launch this script with 
`HF_HOME=new_hf_cache_dir KERAS_HOME=new_keras_cache_dir python examples/singlehost/full_finetuning_example.py`

E.g. `HF_HOME=/dev/shm/temp/hf KERAS_HOME=/dev/shm/temp/keras python examples/singlehost/full_finetuning_example.py`
"""

import os

os.environ["KERAS_BACKEND"] = "jax"
import keras
import ray
from kithara import (
    MaxTextModel,
    Dataloader,
    TextCompletionDataset,
    Trainer,
    Checkpointer,
)
from examples.example_datasets import example_datasets
import jax

config = {
    "model_handle": "hf://google/gemma-2-9b",
    "tokenizer_handle": "hf://google/gemma-2-9b",
    "seq_len": 4096,
    "precision": "mixed_bfloat16",
    "training_steps": 200,
    "eval_steps_interval": 100,
    "log_steps_interval": 1,
    "per_device_batch_size": 1,
    "max_eval_samples": 50,
    "model_output_dir": "gs://bucket_name/ckpt/",
    "learning_rate": 5e-5,
}


def run_workload(
    train_source: ray.data.Dataset,
    eval_source: ray.data.Dataset,
    dataset_is_sharded_per_host: bool,
):

    # Log TPU device information
    devices = jax.devices()
    print(f"Available devices: {devices}")

    # Create Model
    model = MaxTextModel.from_preset(
        preset_handle=config["model_handle"],
        seq_len=config["seq_len"],
        per_device_batch_size=config["per_device_batch_size"],
        precision=config["precision"],
        scan_layers=True,
    )

    # Create Keras optimizer
    optimizer = keras.optimizers.AdamW(
        learning_rate=config["learning_rate"],
        weight_decay=0.01,
    )

    # Create Dataset
    train_dataset = TextCompletionDataset(
        train_source,
        tokenizer_handle=config["tokenizer_handle"],
        max_seq_len=config["seq_len"],
    )
    eval_dataset = TextCompletionDataset(
        eval_source,
        tokenizer_handle=config["tokenizer_handle"],
        max_seq_len=config["seq_len"],
    )

    # Create Dataloaders
    train_dataloader = Dataloader(
        train_dataset,
        per_device_batch_size=config["per_device_batch_size"],
        dataset_is_sharded_per_host=dataset_is_sharded_per_host,
    )
    eval_dataloader = Dataloader(
        eval_dataset,
        per_device_batch_size=config["per_device_batch_size"],
        dataset_is_sharded_per_host=dataset_is_sharded_per_host,
    )

    # Create Checkpointer
    checkpointer = Checkpointer(
        config["model_output_dir"], model=model, save_interval_steps=20, max_to_keep=5
    )

    # Initialize trainer
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        train_dataloader=train_dataloader,
        eval_dataloader=eval_dataloader,
        steps=config["training_steps"],
        eval_steps_interval=config["eval_steps_interval"],
        log_steps_interval=config["log_steps_interval"],
        max_eval_samples=config["max_eval_samples"],
        checkpointer=checkpointer,
    )

    # Start training
    trainer.train()

    # Generate text after training
    pred = model.generate(
        "What is your name?",
        max_length=30,
        tokenizer_handle=config["model_handle"],
        skip_special_tokens=True,
        return_decoded=True,
        strip_prompt=True,
    )
    print(f"Tuned model generated {pred}")

    # Save model in HuggingFace format
    model.save_in_hf_format(config["model_output_dir"] + "hf/")


if __name__ == "__main__":
    train_ds, eval_ds = example_datasets("finetune_toy")
    run_workload(
        train_ds,
        eval_ds,
        dataset_is_sharded_per_host=False,
    )
