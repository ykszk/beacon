import json
import random
import ast
import os
from tqdm import tqdm
from ipdb import set_trace
from calls import retrieval
from collections import defaultdict
from datasets import load_dataset, load_from_disk
from nltk.tokenize.punkt import PunktSentenceTokenizer
from calls import llama_call
from anthropic import HUMAN_PROMPT, AI_PROMPT
from prompts import common, chemprot
from constants import OUTPUT_DIR

def main():
    all_responses = defaultdict(dict)
    prompt = chemprot.GPT_TEXT
    dataset = load_dataset("bigbio/chemprot")["test"]
    output = OUTPUT_DIR / "final_zs/chemprot/llama/zs_text_json_100_for_retrieval.json"

    extracted_entities = json.load(open(output))
    print(len(extracted_entities))
    retriever = retrieval.KnowledgeRetrieval()

    count = 0
    synerr = 0
    keyerr = 0

    for item in tqdm(dataset):
        iid = item["pmid"]
        text = item["text"]
        sent_text = []
        for start, end in PunktSentenceTokenizer().span_tokenize(text):
            sentence = text[start:end]
            sent_text.append(sentence)

        extracted_abs = extracted_entities[iid]
        sent_response = {}
        sent_messages = {}
        for sent_id, text in enumerate(sent_text):
            
            messages = []
            # remove human here? 
            messages += [f"<human>: {prompt}"]
            messages += [f"<human>: {text}" ]

            try: 
                extracted_sent = extracted_abs[str(sent_id)]
                #extracted_sent = ast.literal_eval(extraction)
                if isinstance(extracted_sent, dict):
                    messages += [f"<bot>:",json.dumps(
                                {
                                    k: v
                                    for k, v in extracted_sent.items()
                                    if k in ("chemical", "protein")
                                }
                            ),
                    ]
                    list_to_retrieve = []
                    for types, entities in extracted_sent.items():
                        list_to_retrieve += entities

            
                    ent_definitions = retriever.link_with_umls(list_to_retrieve)

                    content = ""
                    for key, value in ent_definitions.items():
                        content += f"{key}:\n{value}\n"
                
                else:
                    synerr += 1
                    list_to_retrieve = [] 
                    content = ""
            
            except Exception as e:
                extracted_sent = {"chemical" : [], "protein" : []}
                synerr += 1
                list_to_retrieve = [] 
                content = ""

            noun_definitions = retriever.extract_noun_phrases_and_link_with_umls_remove_repeats(text, list_to_retrieve)

            content_noun = ""
            for key, value in noun_definitions.items():
                content_noun += f"{key}:\n{value}\n"

            if content == "":
                if content_noun == "":
                    messages += [f"<human>: {common.PROMPT_END_NO_DEF}"]
                else: 
                    messages += [f"<human>: {common.PROMPT_NOUN + content_noun +  common.PROMPT_END + text}"]
            else:
                if content_noun == "":
                    messages += [f"<human>: {common.PROMPT_RET + content +  common.PROMPT_END + text}"]
                else:   
                    messages += [f"<human>: {common.PROMPT_RET + content + common.PROMPT_NOUN + content_noun +  common.PROMPT_END + text}"]


            response = llama_call.generate_text(messages,  temperature=0, max_tokens=256)
            

            sent_response[sent_id] = response
            sent_messages[sent_id] = messages
  

        all_responses[iid]["responses"] = sent_response
        all_responses[iid]["messages"] = sent_messages
        
        count += 1

        if (count % 100 == 0) or (count == len(dataset)):
            print(f"Num of test datapoints: {count}")
            path = OUTPUT_DIR / "/final_ret/chemprot/llama/"
            isExist = os.path.exists(path)
            if not isExist:
                print("created path")
                os.makedirs(path)
            with open(
                OUTPUT_DIR / f"/final_ret/chemprot/llama/zs_stC_ret_{count}.json",
                "w",
            ) as f:
                json.dump(all_responses, f)


if __name__ == "__main__":
    main()
