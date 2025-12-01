from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import Optional, List

# load kb
with open("knowledgeBase.json", "r", encoding="utf-8") as f:
    KB = json.load(f)

BMI_RULES = KB["bmi_rules"]
CONDITION_RULES = KB["condition_rules"]
FOODS = KB["foods"]

# setup fastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# input 
class UserInput(BaseModel):
    height_cm: float
    weight_kg: float
    diabetes: bool = False
    hypertension: bool = False
    vegetarian: bool = False
    allergy_susu: bool = False
    allergy_seafood: bool = False

# helper function
def hitung_bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100.0
    return weight_kg / (height_m ** 2)

def hitung_ibw(height_cm: float, target_bmi: float = 24.0) -> float:
    height_m = height_cm / 100.0
    return target_bmi * (height_m ** 2)

def pilih_bmi_rule(bmi: float) -> Optional[dict]:
    for rule in BMI_RULES:
        bmi_min = rule.get("bmi_min")
        bmi_max = rule.get("bmi_max")

        if bmi_min is not None and bmi < bmi_min:
            continue
        if bmi_max is not None and bmi > bmi_max:
            continue
        return rule
    return None

def inference_engine(facts: dict):
    diet_tags = set()
    tips: List[str] = []

    for rule in CONDITION_RULES:
        fact_name = rule["condition_fact"]
        expected_value = rule["value"]
        if facts.get(fact_name) == expected_value:
            for t in rule.get("diet_tags_add", []):
                diet_tags.add(t)
            tips.extend(rule.get("tips", []))

    return list(diet_tags), tips

def pilih_rekomendasi_makanan(diet_tags: List[str], vegetarian: bool,allergy_susu: bool, allergy_seafood: bool):
    hasil = []

    for food in FOODS:
        tags = food.get("tags", [])

        if vegetarian and "vegetarian" not in tags:
            continue

        if allergy_susu and "dairy" in tags:
            continue

        if allergy_seafood and "seafood" in tags:
            continue

        cocok = True
        for tag in diet_tags:
            if tag == "low_sugar" and "high_sugar" in tags:
                cocok = False
            if tag == "low_glycemic" and "not_low_glycemic" in tags:
                cocok = False
            if tag == "low_sodium" and "high_sodium" in tags:
                cocok = False

        if cocok:
            hasil.append(food)

    return hasil[:5]


@app.post("/consult")
def consult(user: UserInput):
    # hitung bmi & ibw
    bmi = hitung_bmi(user.weight_kg, user.height_cm)
    target_bmi = 24.0
    ibw = hitung_ibw(user.height_cm, target_bmi)

    # facts
    facts = {
        "BMI": bmi,
        "diabetes": user.diabetes,
        "hypertension": user.hypertension,
        "vegetarian": user.vegetarian,
        "allergy_susu": user.allergy_susu,
        "allergy_seafood": user.allergy_seafood,
    }

    # inference
    bmi_rule = pilih_bmi_rule(bmi)

    if bmi_rule:
        protein_per_kg_ibw = bmi_rule["protein_g_per_kg_ibw"]
        cal_min_per_kg = bmi_rule["calories_kcal_per_kg_ibw_min"]
        cal_max_per_kg = bmi_rule["calories_kcal_per_kg_ibw_max"]
    else:
        # fallback jika BMI < 30 atau tidak ter-cover kb
        protein_per_kg_ibw = 1.2
        cal_min_per_kg = 25
        cal_max_per_kg = 30

    # hitung kebutuhan kalori dan protein
    protein_grams = protein_per_kg_ibw * ibw
    calories_min = cal_min_per_kg * ibw
    calories_max = cal_max_per_kg * ibw

    # cond rules
    diet_tags, tips = inference_engine(facts)

    # rekom makanan
    rekomendasi_makanan = pilih_rekomendasi_makanan(
        diet_tags=diet_tags,
        vegetarian=user.vegetarian,
        allergy_susu=user.allergy_susu,
        allergy_seafood=user.allergy_seafood
    )

    # traget weight dari ibw
    target_weight = ibw

    # respon
    return {
        "bmi": round(bmi, 2),
        "bmi_category": (
            "Underweight" if bmi < 18.5 else
            "Normal" if bmi < 25 else
            "Overweight" if bmi < 30 else
            "Obese"
        ),
        "ibw_kg": round(ibw, 2),
        "target_bmi": target_bmi,
        "target_weight_kg": round(target_weight, 2),
        "protein_grams_per_day": round(protein_grams, 1),
        "calories_min_per_day": round(calories_min),
        "calories_max_per_day": round(calories_max),
        "selected_bmi_rule": bmi_rule["id"] if bmi_rule else None,
        "diet_tags": diet_tags,
        "tips": tips,
        "recommended_foods": [
            {
                "id": food["id"],
                "name": food["name"],
                "per_100g": food["per_100g"],
                "tags": food["tags"]
            }
            for food in rekomendasi_makanan
        ]
    }
