import os
import ollama
from config import OLLAMA_MODEL

def generate_ceo_response(question: str, evidence: str, model:str | None = None)  ->str: 
    selected_model = model or os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)

    prompt = F"""
You are SAP'S Chief Strategy Officer advising teh CEO.
Use only the evidence below. If the evidnce is weak or incomplte, say that cleary.

User question:
{question}

Evidence:
{evidence}

Return the answer in this exact structure:

#Direct Answer
Give a practical executive answer in 4-6 short paragraphs.

#Key Findings
- List the most important evidence-backed findings.

#Opportunities
- Opportunities title | impact level | confidence score | evidence reference.

#Risks
- Risk title | severity level | confidence score| evidence reference.

#Strategic Recommendations
For exactly 3 recommendations, include:
- Recommendation
- Priority: High /  Medium /  Low
- Supporting evidence
- Expected impact
- Risk level

# Ceo Briefing
What happened?
why does it matter?
what should management do next?

# Confidence score
Give a score from 1-10 and explain briefly.
"""
    response = ollama.chat(
        model = selected_model,
        messages=[{"role":"user", "content": prompt}],
        options= {
            "temperature": 0.2,
            "num_predict": 900,
        },
        
    )
    return response["message"]["content"]