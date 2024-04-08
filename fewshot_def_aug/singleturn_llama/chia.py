import json
import random
import utils
import os
from calls import llama_call
from tqdm import tqdm
from ipdb import set_trace
from datasets import load_from_disk
from calls import retrieval
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from prompts import common, chia
from constants import OUTPUT_DIR

entities_map = {
    "condition": "list of entities",
    "device": "list of entities",
    "drug": "list of entities",
    "measurement": "list of entities",
    "mood": "list of entities",
    "multiplier": "list of entities",
    "negation": "list of entities",
    "observation": "list of entities",
    "person": "list of entities",
    "procedure": "list of entities",
    "qualifier": "list of entities",
    "reference_point": "list of entities",
    "scope": "list of entities",
    "temporal": "list of entities",
    "value": "list of entities",
    "visit": "list of entities",
}

HUMAN_PROMPT = "<human>:"
AI_PROMPT = "<bot>:"


def run_fewshot(k, seed):
    print(seed, k)
    all_responses = {}
    prompt = chia.TEXT_JSON
    dataset = load_from_disk(
        "replace with the chia data split path"
    )
    print(len(dataset))
    output_formatter = utils.OutputFormatter(dataset="chia", seed=seed)
    output = OUTPUT_DIR / f"/final_fs_subsample/chia/llama/zs_text_json_5shot_seed{seed}_100.json"
    extracted_entities = json.load(open(output))
    retriever = retrieval.KnowledgeRetrieval()
    
    count = 0
    synerr = 0
    keyerr = 0
    for item in tqdm(dataset):
        iid = item["id"]
        all_text = item["text"]
        sent_text = filter(None, all_text.split("\n"))

        sent_response = {}
        if item["id"][-3:] == "exc":
            criterion = """
                Given the definitions of entities and following Exclution criterion for clinical trail, """
        else:
            criterion = """
                Given the following Inclusion criterion for clinical trail, """
        for sent_id, this_text in enumerate(sent_text):

            try:
                extracted_sent = extracted_abs[str(sent_id)]
                #extracted_sent = ast.literal_eval(extracted_sent_raw.strip())
            except Exception as e:
                synerr += 1
                extracted_sent = {'condition': [],
                'device': [],
                'drug': [],
                'measurement' : [],
                'observation' : [],
                'person' : [],
                "procedure" : [],
                "visit": [],
                "temporal" : [],
                "value" : [],
                "scope" : [],
                "negation" : [],
                "qualifier" : [],
                "multiplier" : [],
                "reference_point" : [],
                "mood": []}

            key_id = iid + "-" + str(sent_id)
            formatted_shots = output_formatter.format_output(key_id=key_id, k=k)
            random.shuffle(formatted_shots)
            messages = []
            messages += [prompt]
            for i in range(len(formatted_shots)):

                shot_text = formatted_shots[i]["text"]
                messages += [HUMAN_PROMPT + " Example Shot:" +  shot_text]
                # list_to_retrieve = []
                # list_to_retrieve += formatted_shots[i]["chemicals"]
                # list_to_retrieve += formatted_shots[i]["diseases"]
                #
                # noun_definitions = retriever.extract_noun_phrases_and_link_with_umls_remove_repeats(shot_text, list_to_retrieve)
                # ent_definitions = retriever.link_with_umls(list_to_retrieve)
                #
                # content = ""
                # for key, value in ent_definitions.items():
                #     content += f"{key}: {value}\n"
                #
                # content_noun = ""
                # for key, value in noun_definitions.items():
                #     content_noun += f"{key}: {value}\n"
                #
                # if content == "":
                #     if content_noun == "":
                #         messages += [HUMAN_PROMPT +  prompt_end_no_def + "\nOutput:" ]
                #     else:
                #         messages += [HUMAN_PROMPT + prompt_ent + content_noun +  prompt_end + "\n Sentence: " + this_text + "\nOutput:" ]
                # else:
                #     if content_noun == "":
                #         messages += [HUMAN_PROMPT + prompt_ent + content +  prompt_end + "\n Sentence: " + this_text + "\nOutput:" ]
                #     else:
                #         messages += [HUMAN_PROMPT + prompt_ent + content + content_noun +  prompt_end + "\n Sentence: " + this_text + "\nOutput:" ]
                #

                messages += (str(json.dumps(
                                {
                                    k: v
                                    for k, v in formatted_shots[i].items()
                                    if k in ("condition",
                                        "device",
                                        "drug",
                                        "measurement",
                                        "mood",
                                        "multiplier",
                                        "negation",
                                        "observation",
                                        "person",
                                        "procedure",
                                        "qualifier",
                                        "reference_point",
                                        "scope",
                                        "temporal",
                                        "value",
                                        "visit",)
                                }
                            ),
                        ),
                )

            messages += [HUMAN_PROMPT + " Sentence (only extract from here): " + this_text]
            
            list_to_retrieve_text = []
            for types, entities in extracted_sent.items():
                list_to_retrieve_text += entities
            
            noun_definitions = retriever.extract_noun_phrases_and_link_with_umls_remove_repeats(this_text, list_to_retrieve_text)
            ent_definitions = retriever.link_with_umls(list_to_retrieve_text)

            content = ""
            for key, value in ent_definitions.items():
                content += f"{key}: {value}\n"

            content_noun = ""
            for key, value in noun_definitions.items():
                content_noun += f"{key}: {value}\n"


            if content == "":
                if content_noun == "":
                    messages += [HUMAN_PROMPT +  common.PROMPT_END_NO_DEF + "\nOutput:" ]
                else: 
                    messages += [HUMAN_PROMPT + common.PROMPT_ENT + content_noun +  common.PROMPT_END+ "\n Sentence: " + this_text + "\nOutput:" ]
            else:
                if content_noun == "":
                    messages += [HUMAN_PROMPT + common.PROMPT_ENT + content +  common.PROMPT_END+ "\n Sentence: " + this_text + "\nOutput:" ]
                else:   
                    messages += [HUMAN_PROMPT + common.PROMPT_ENT + content + content_noun +  common.PROMPT_END+ "\n Sentence: " + this_text + "\nOutput:" ]

        
            messages = str(messages)
            response = llama_call.generate_text(messages, temperature=0, max_tokens=256)

            sent_response[sent_id] = response
            
        all_responses[iid] = sent_response
        count += 1

    if (count % 100 == 0) or (count == len(dataset)):
        print(f"Num of test datapoints: {count}")
        path = OUTPUT_DIR / "/final_fs_ret/chia/llama/"
        isExist = os.path.exists(path)
        if not isExist:
            print("creating path")
            os.makedirs(path)
        with open(
            OUTPUT_DIR / f"/final_fs_ret/chia/llama/fs_stC_{k}shot_seed{seed}_{count}.json",
            "w",
        ) as f:
            json.dump(all_responses, f)


def main():
    pass


if __name__ == "__main__":
    main()
