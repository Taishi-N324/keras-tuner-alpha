import jax.numpy as jnp
import torch
import numpy as np 
from kithara.utils.torch_utils import convert_jax_weight_to_torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import jax
from tabulate import tabulate
import torch.nn.functional as F


def check_arrays_match(arrayA, arrayB, atol=0.01):
    """
    Compare two sets of arrays for equality within the specified absolute tolerance.
    
    This function handles both PyTorch tensors and JAX arrays, automatically
    converting between the two if necessary. If the arrays don't match within
    the specified tolerance, it prints detailed information about the mismatches
    and raises a AssertionError.
    
    Args:
        arrayA (Union[torch.Tensor, jax.Array]): First set of arrays to compare
        arrayB (Union[torch.Tensor, jax.Array]): Second set of arrays to compare
        atol (float, optional): Absolute tolerance for comparison. Defaults to 0.01
    
    Raises:
        AssertionError: If the arrays don't match within the specified tolerance
    """
    # Determine types and convert if needed
    is_A_torch = isinstance(arrayA, torch.Tensor)
    is_B_torch = isinstance(arrayB, torch.Tensor)
    
    # If one is torch and one is jax, convert jax to torch
    if is_A_torch and not is_B_torch:
        arrayB = convert_jax_weight_to_torch(arrayB)
    elif is_B_torch and not is_A_torch:
        arrayA = convert_jax_weight_to_torch(arrayA)
    
    # If both are now torch tensors
    if isinstance(arrayA, torch.Tensor):
        max_diff = torch.max(torch.abs(arrayA-arrayB))
        print("Maximum absolution difference:", max_diff)
        if not torch.allclose(arrayA, arrayB, atol=atol):
            is_close = torch.isclose(arrayB, arrayA, atol=atol)
            mismatch_indices = ~is_close
            print(f"Number of mismatch elements in {arrayB.shape}", mismatch_indices.sum().item())
            print(arrayA[mismatch_indices])
            print(arrayB[mismatch_indices])
            raise AssertionError(f"Failed to match arrays.")
        
    # If both are still jax arrays
    else:
        max_diff= jnp.max(jnp.abs(arrayA-arrayB))
        print("Maximum absolution difference:", max_diff)
        if not jnp.allclose(arrayA, arrayB, atol=atol):
            is_close_idx = jnp.isclose(arrayB, arrayA, atol=atol)
            print(f"Number of mismatch elements in {arrayB.shape}", len(arrayB[is_close_idx==False]))
            print(arrayA[is_close_idx==False])
            print(arrayB[is_close_idx==False])
            raise AssertionError(f"Failed to match arrays.")
    
def check_predicted_tokens_match(logits_a, logits_b, tolerance=0.05):
    """Compares the top predicted tokens from each set of logits and ensures their 
    disagreement rate doesn't exceed the tolerance threshold. Raises an AssertionError 
    if the disagreement is too high.
    
    Args:
        logits_a (jax.Array | torch.Tensor | np.ndarray): First set of model output logits
        logits_b (jax.Array | torch.Tensor | np.ndarray): Second set of model output logits to compare against logits_a
        tolerance (float, optional): Maximum allowed fraction of token prediction disagreements,
            must be between 0.0 and 1.0. Defaults to 0.05 (5%).
                        
    Examples:
        >>> logits1 = get_model_output(input1)
        >>> logits2 = get_model_output(input2) 
        >>> check_predicted_tokens_match(logits1, logits2, tolerance=0.03)  # Allows 3% disagreement
    """
    # Validate tolerance input
    if not 0.0 <= tolerance <= 1.0:
        raise ValueError("Tolerance must be between 0.0 and 1.0")
    
    metrics = get_logits_comparison_metrics(logits_a, logits_b)
    disagreement_rate = metrics["disagreement_top1"]
    
    if disagreement_rate > tolerance:
        raise AssertionError(
            f"Token prediction mismatch: {disagreement_rate:.1%} of tokens disagree "
            f"(exceeds tolerance of {tolerance:.1%})"
        )
    
def get_logits_comparison_metrics(logitsA, logitsB):
    """
    Calculate various comparison metrics between two sets of logits.
    
    This function computes several metrics to compare the similarity and differences
    between two sets of logits, including KL divergence, absolute differences,
    and agreement in top-k predictions.
    
    Args:
        logitsA (jax.Array | torch.Tensor | np.ndarray): First set of logits to compare
        logitsB (jax.Array | torch.Tensor | np.ndarray): Second set of logits to compare
    
    Returns:
        dict: A dictionary containing the following metrics:
            - max_kl_div: Maximum KL divergence between probability distributions
            - abs_diff: Maximum absolute difference between probabilities
            - disagreement_top5: Proportion of positions where top-5 predictions differ
            - disagreement_top1: Proportion of positions where top-1 predictions differ
    
    Notes:
        The function also prints a formatted table of the metrics using tabulate.
    """

    if isinstance(logitsA, jax.Array) :
        logitsA = convert_jax_weight_to_torch(logitsA)
    if isinstance(logitsA, np.ndarray):
        logitsA = torch.tensor(logitsA)
    if isinstance(logitsB, jax.Array):
        logitsB = convert_jax_weight_to_torch(logitsB)
    if isinstance(logitsB, np.ndarray):
        logitsB = torch.tensor(logitsB)
    
    # Calculate probabilities
    probs_A = F.softmax(logitsA, dim=-1)
    probs_B = F.softmax(logitsB, dim=-1)

    # Calculate metrics
    kl_div = F.kl_div(torch.log(probs_B), probs_A, reduction='sum', log_target=False)
    max_abs_diff = torch.abs(probs_A - probs_B).max()

    # Calculate top-k agreement metrics
    sorted_logits_A = torch.argsort(logitsA, dim=1)
    sorted_logits_B = torch.argsort(logitsB, dim=1)
    ranking_A_top5 = sorted_logits_A[:, -5:]
    ranking_B_top5 = sorted_logits_B[:, -5:]
    disagreement_top5 = torch.mean((
        (torch.abs(ranking_B_top5 - ranking_A_top5) > 0).sum(dim=1) > 0
    ).float())

    ranking_A_top1 = sorted_logits_A[:, -1:]
    ranking_B_top1 = sorted_logits_B[:, -1:]
    disagreement_top1 = torch.mean((
        (torch.abs(ranking_B_top1 - ranking_A_top1) > 0).sum(dim=1) > 0
    ).float())

    metrics = {
        "max_kl_div": float(torch.max(kl_div)),
        "abs_diff": float(max_abs_diff),
        "disagreement_top5": float(disagreement_top5),
        "disagreement_top1": float(disagreement_top1),
    }
    
    table = [[key, value] for key, value in metrics.items()]
    print(tabulate(table, headers=["Metric", "Value"], tablefmt="orgtbl"))
    return metrics



def get_hf_logits(model_id, prompt_text, target_length, return_input_ids=True, model=None):
    """
    Get logits from a HuggingFace model for a given prompt.
    
    This function loads a specified HuggingFace model, tokenizes the input prompt,
    and returns the model's logits.
    
    Args:
        model_id (str): The HuggingFace model identifier to load
        prompt_text (str): The input text to process
        target_length (int): Maximum length of the tokenized input
        return_input_ids (bool, optional): Whether to return the tokenized input IDs. Defaults to True
        model (AutoModelForCausalLM): The HuggingFace model instance. When passed, 
            this model will be used directly instead of creating a new model. A 
            model_id is still required for loading the tokenizer. 
    
    Returns:
        If return_input_ids is True:
            tuple: (input_ids, logits) where input_ids is a torch.Tensor and
                  logits is a numpy array of shape [batch_size, seq_len, vocab_size]
        If return_input_ids is False:
            numpy.ndarray: The model's logits
    """

    # Initialize HuggingFace model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if model == None:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.float32, output_hidden_states=True
        )

    # Tokenize input
    input_ids = tokenizer.encode(prompt_text, return_tensors="pt")[
        :, :target_length
    ]

    # Get HuggingFace model outputs
    with torch.no_grad():
        outputs = model(input_ids)
        logits_B = outputs.logits.cpu().numpy().astype("float32")

    if return_input_ids:
        return input_ids, logits_B
    return logits_B


def get_maxtext_model_input(input_ids, per_device_batch_size=1):
    """
    Convert tokens into the input format expected by MaxText models.
        
    Args:
        input_ids (numpy.ndarray): Array of token IDs with shape [B, S] where
            B is batch size and S is sequence length. Note that only the first
            sequence in the batch is used.
        per_device_batch_size (int, optional): Batch size per device. Defaults to 1.
    
    Returns:
        dict: A dictionary containing:
            - tokens: Batched input tokens
            - segment_ids: Segment IDs for the input
            - positions: Position encodings for the input
            
    Notes:
        The function replicates the first sequence in input_ids to match the
        required global batch size (per_device_batch_size * number of devices).
    Usage: 
        input_ids = jax.numpy.array([[1,2,3]])
        maxtext_input = get_maxtext_model_input(input_ids)
        model = MaxTextModel.from_preset(
            preset_handle=f"hf://{MODEL_ID}",
            seq_len=10,
            per_device_batch_size=1,
        )
        logits_maxtext, _ = model.stateless_call(
            model.trainable_variables,
            model.non_trainable_variables,
            maxtext_input,
        )
    """
    global_batch_size = jax.device_count() * per_device_batch_size
    B, S = input_ids.shape
    ids = np.asarray(input_ids.tolist()[0], dtype=np.int32)
    ids = jnp.stack([ids for _ in range(global_batch_size)])

    decoder_segment_ids = jnp.ones((global_batch_size, S))
    decoder_positions = jnp.stack(
        [
            jnp.arange(S, dtype=jnp.int32)
            for _ in range(global_batch_size)
        ]
    )
    return {
            "tokens": ids,
            "segment_ids": decoder_segment_ids,
            "positions": decoder_positions,
        }


def get_kerashub_model_input(input_ids):
    """
    Convert tokens into the input format expected by KerasHub models.
        
    Args:
        input_ids (numpy.ndarray): Array of token IDs with shape [B, S] where
            B is batch size and S is sequence length. Note that only the first
            sequence in the batch is used.
    
    Returns:
        dict: A dictionary containing:
            - tokens_ids: Batched input tokens
            - padding_mask: Padding mask of all 1s for the input            
    """
    B, S = input_ids.shape
    padding_mask = jnp.ones((B, S))
    return {
            "token_ids": input_ids,
            "padding_mask": padding_mask,
        }
