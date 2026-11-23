# How Large Language Models (LLMs) Work — In Plain Words

A Large Language Model (LLM) is essentially a sophisticated **next-token prediction engine** trained on massive amounts of text. Instead of looking up answers in a fixed database, it learns statistical patterns of language—grammar, facts, reasoning steps, and context—and generates responses one piece (token) at a time.

---

## 1. End-to-End LLM Pipeline Diagram

```text
+-----------------------+     +------------------------+     +---------------------------+
|  1. User Prompt +     | --> |  2. Tokenizer          | --> |  3. Token Embeddings +    |
|  Retrieved GST Rules  |     |  (Splits text into     |     |  Positional Encoding      |
|  (Context Window)     |     |   sub-word IDs)        |     |  (Text -> Math Vectors)   |
+-----------------------+     +------------------------+     +---------------------------+
                                                                           |
                                                                           v
+-----------------------+     +------------------------+     +---------------------------+
|  6. Final Plain-      | <-- |  5. Sampling /         | <-- |  4. Transformer Blocks    |
|  Language GST Answer  |     |  Decoding (Softmax +   |     |  (Self-Attention + Feed-  |
|  (Detokenized Text)   |     |  Temperature/Top-P)    |     |  Forward Neural Layers)   |
+-----------------------+     +------------------------+     +---------------------------+
```

---

## 2. Step-by-Step Breakdown

1. **Tokenization:** Text is broken into small chunks called **tokens** (words, sub-words, or punctuation) and mapped to numeric IDs. For example, `"GSTSaral"` might split into `["GST", "Sar", "al"]`.
2. **Embeddings & Position:** Each token ID is converted into a dense list of numbers (**vector**) capturing its meaning, combined with its position in the sentence so word order is preserved.
3. **Self-Attention (The Core Magic):** Inside stacked **Transformer** layers, every token looks at every other token in the prompt to weigh what matters most. In *"What is the new GST rate on UHT milk?"*, attention links `"new GST rate"` directly to `"UHT milk"`.
4. **Probability Distribution & Decoding:** After passing through all layers, the model predicts a probability score for every token in its vocabulary for what comes next. Decoding settings like **temperature** (low = deterministic/factual, high = creative) pick the next token, append it to the input, and repeat until the answer is complete.
5. **Why Retrieval (RAG) Matters for GSTSaral:** An LLM only knows what was inside its training data up to its cutoff date and can guess ("hallucinate") when unsure. By retrieving verified 56th GST Council rules first and injecting them into the prompt's **context window**, GSTSaral grounds the LLM in official numbers—and instructs it to say *"I don't know"* when the data isn't there.

---

## 3. 10 Real GSTSaral User Questions

*(Questions 1–6 come from our GSTSaral project card; **Q6** is intentionally outside our dataset to test abstention/honesty, followed by 4 additional shopkeeper & MSME queries.)*

1. **Q1 (Project Card):** What is the new GST rate on toilet soap bars after the 56th GST Council meeting?
2. **Q2 (Project Card):** Did the GST rate on Ultra-High Temperature (UHT) milk and packaged paneer drop to Nil (0%)?
3. **Q3 (Project Card):** How much GST applies to school notebooks, exercise books, and pencils now?
4. **Q4 (Project Card):** What changed in the GST slab for bicycles and bicycle parts, and from what date?
5. **Q5 (Project Card):** What is the updated GST rate on butter, ghee, and packaged namkeens?
6. **Q6 (Project Card — Out-of-Scope / Unanswerable from Current Data):** What is the exact GST late fee penalty and interest calculation for filing GSTR-9C three months late in FY 2025-26? *(Cannot be answered from our current 56th Council everyday-item rate dataset.)*
7. **Q7:** Are hair oil and shampoos taxed at 5% or 18% GST from September 22, 2025?
8. **Q8:** Do Indian breads like packaged chapati, roti, and paratha attract any GST now?
9. **Q9:** What was the old GST rate versus the new GST rate on chocolates and cornflakes?
10. **Q10:** Which everyday stationery items moved from 12% GST down to 0% (Nil) GST?
