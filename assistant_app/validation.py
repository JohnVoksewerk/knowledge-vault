def validate_prompt(prompt: str, max_prompt_chars: int) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Prompten er tom.")
    if len(cleaned) < 3:
        raise ValueError("Prompten er for kort til at give et brugbart svar.")
    if len(cleaned) > max_prompt_chars:
        raise ValueError(f"Prompten er for lang. Maks laengde er {max_prompt_chars} tegn.")
    return cleaned

