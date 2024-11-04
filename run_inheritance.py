import shutil
import os
import json
import subprocess
from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput
from src.utils import run_llm, extract_content_between_tags
from src.dataset_preparation import prepare_dataset
import pandas as pd

def copy_source_to_workspace(src, dst):
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"Successfully copied '{src}' to '{dst}'")
    except Exception as e:
        print(f"Error: {e}")

def get_dataset(research_context, proposition_idea, workspace_directory):
    dataset_prompt_template = """
    Research Context: {research_context}
    Proposition Idea: {proposition_idea}

    Your final goal is to implement a Proposition Idea and design experiments to validate its feasibility based on the Research Context. To achieve this, generate search query for obtaining text datasets from HuggingFace using an LLM. This prompt should explicitly state the purpose and objectives of the research, what the Proposition Idea is, and which datasets should be retrieved to validate it.

    query will be used as follows:
    from huggingface_hub import HfApi
    api = HfApi()
    results = list(api.list_datasets(search=query, sort="downloads", direction=-1, limit=max_results))

    Note that query input to `search` is a string that will be contained in the returned datasets.

    The query should be a word that is likely included in the desired dataset name but unlikely to be found in unrelated dataset names. It should primarily consist of terms related to machine learning tasks or concepts. In particular, it should include words associated with the operations required for validating the method you proposed with the dataset or task.

    Generate only one query and the query should be single word contined in the text dataset name.

    <query>
    "..."
    </query>
    """

    dataset_prompt = dataset_prompt_template.format(research_context=research_context, proposition_idea=proposition_idea)
    dataset_search_query_with_tags = run_llm(model_name="gemma2:9b", message=dataset_prompt)
    dataset_search_query = extract_content_between_tags(dataset_search_query_with_tags, "<query>", "</query>")
    dataset_name, dataset = prepare_dataset(dataset_search_query)
    dataset_dir = os.path.join(workspace_directory, "dataset")
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir)
    dataset.save_to_disk(dataset_dir)

    return dataset_name, dataset

def save_prompts(prompts, filename):
    with open(filename, "w") as f:
        json.dump(prompts, f)

def initialize_coder(workspace_directory, coder_llm_name):
    visible_file_names = [f"{workspace_directory}/algorithm.py", f"{workspace_directory}/inheritance_experiment.py"]
    open(f"{workspace_directory}/aider.txt", "w").close()
    io = InputOutput(yes=True, chat_history_file=f"{workspace_directory}/aider.txt")
    coder_model = Model(coder_llm_name)
    return Coder.create(main_model=coder_model, fnames=visible_file_names, io=io, stream=False, use_git=False, edit_format="diff")

def run_experiment(coder, prompt, workspace_directory, timeout=600):
    coder.run(prompt)
    cwd = os.path.abspath(workspace_directory)
    command = ["uv", "run", "python", "inheritance_experiment.py"]
    return subprocess.run(command, cwd=cwd, stderr=subprocess.PIPE, text=True, timeout=timeout)

def main():
    # Configuration
    source_directory = "/root/src"  # "/root/fukuro-researcher/src"
    workspace_directory_base = "/root/workspace"  # "/root/fukuro-researcher/workspace"
    workspace_directory = os.path.join(workspace_directory_base, source_directory.split("/")[-1])
    if not os.path.exists(workspace_directory):
        os.makedirs(workspace_directory)
    coder_llm_name = "claude-3-5-sonnet-20240620" # "gemma2:9b"
    max_edit_trials = 10

    # Research context and proposition
    research_context = """
    With the growing availability of smaller yet powerful local language models such as google/gemma-2-2b-it, there is a growing interest in maximizing their performance while keeping computational and resource costs low. However, the challenge lies in maintaining competitive performance levels across different NLP tasks without access to the scale of training resources or architecture size that larger LLMs enjoy. Existing optimization techniques such as low-rank adaptation (LoRA) or prompt-tuning have improved smaller models' utility, but identifying ways to better exploit such models remains an open problem. Additionally, the balance between task generalization and task-specific fine-tuning presents a crucial tradeoff for real-world usability, especially in constrained environments such as edge computing or private deployments.
    """

    proposition_idea = """
    We propose Dynamic Prompt Assembly (DPA), a novel technique where prompts are generated dynamically based on the model's intermediate outputs and task requirements. Instead of relying on static prompt templates, DPA allows the model to iteratively refine and assemble its own prompts by evaluating intermediate outputs during inference. This self-assembly process introduces a layer of model-driven reasoning at runtime, leading to adaptive performance improvements across diverse tasks. By leveraging lightweight dynamic adjustments, this method ensures performance close to state-of-the-art large models, while remaining feasible for smaller architectures such as gemma-2-2b-it.
    DPA can also serve as an efficient fine-tuning alternative, reducing the need for extensive retraining while allowing the model to specialize incrementally on specific tasks through real-time prompt modulation. This technique promises to bridge the gap between small models' capabilities and real-world demands, offering a pathway to deploy effective, cost-efficient AI solutions.
    """

    # Execute steps
    copy_source_to_workspace(source_directory, workspace_directory)
    dataset_name, dataset = get_dataset(research_context, proposition_idea, workspace_directory)
    df = pd.DataFrame(dataset['train'])

    # show first 1 sample of dataset

    coder = initialize_coder(workspace_directory, coder_llm_name)

    experiment_coding_prompt = """
    Research Context: {research_context}
    Proposition Idea: {proposition_idea}

    Prerequisite:
        Model:
        The base model used in this experiment is google/gemma-2-2b-it.

        Dataset:
        {dataset_name}
        {dataset}

    Code Explanation:
    algorithm.py represents the workflow of a machine learning research that verifies the effectiveness of the proposed method through comparative experiments. Specifically, given the dataset, model, and tokenizer, it executes Algorithm and NewAlgorithm (which is a modified version of Algorithm), and then compares and evaluates their results using compare_and_evaluate_algorithms
    Algorithm represents a typical machine learning workflow where the model is trained on training data and then executed on test data. 
    
    inheritance_experiment.py represents the comparative experiment that validates the effectiveness of the proposed method through the comparison between Algorithm and NewAlgorithm.
    NewAlgorithm inherits from Algorithm and modifies the workflow by overriding train_model, run_model, or both. 
    Researcher implements the proposed idea in NewAlgorithm and the proposition idea and related parts are the only differences between Algorithm and NewAlgorithm.
    This code embodies the idea that "machine learning research that validates a proposal through comparative experiments is an endeavor to determine whether adding a new proposal (NewAlgorithm) to an Algorithm that generates certain output from data yields better results in an expected sense."

    Task Description:
    Please edit inheritance_experiment.py to implement the Proposition Idea and design experiments to validate its feasibility based on the Research Context.
    Your task is to complete the experimental code by editing inheritance_experiment.py.
    Please edit the following parts, but do not change any other parts:

    NewAlgorithm
        To implement the Proposition Idea and design experiments to validate its effectiveness, override one or all methods of Algorithm. For example, if you're proposing a new Optimizer, implement the new optimizer and use it in train_model instead of the existing optimizer. If you're proposing a new neural architecture, implement the new architecture in the Hugging Face format and assign it in the part where self.model = model.to(device) is set in the __init__ method. If you're proposing a prompt technique to improve the zero-shot inference performance of a pre-trained model, implement the prompt technique in the run_model part. In this way, first consider which part of the machine learning workflow the Proposition Idea is addressing, and then implement NewAlgorithm to properly implement and experiment with the proposal. When doing so, make sure to define all the information needed to see if the proposal is superior to existing methods in the expected sense using self.log.

    compare_and_evaluate_algorithms
        Implement evaluation criteria to examine how and in what sense the Proposition Idea is superior to existing methods. For example, if the proposed method is expected to predict better than existing methods, you might compare if the accuracy is higher. Or, if you're proposing an optimization method that's expected to converge faster, you might compare the number of steps it took before the loss reached a certain value. Also, if you're proposing a method with superior interpretability, you might define some metric that shows that the internal representation of the model is more interpretable in some sense and compare that. In this way, consider in what sense the Proposition Idea is expected to be superior to existing methods in relation to the Research Context, and implement evaluation metrics that can compare this.
    """.format(research_context=research_context, proposition_idea=proposition_idea, dataset_name=dataset_name, dataset=df.head(1))

    for i in range(max_edit_trials):
        run_result = run_experiment(coder, experiment_coding_prompt, workspace_directory)

        if run_result.returncode == 0:
            print("Successfully executed")
            break
        else:
            print("Failed to execute")
            error_message = run_result.stderr
            print(error_message)
            experiment_coding_prompt = f"error: {error_message}\nprompt: "

        if i == max_edit_trials - 1:
            print("Failed to execute after max trials")
            break

if __name__ == "__main__":
    main()