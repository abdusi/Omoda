"""Supported NTC components. Foreign-language alternatives are deliberately limited to English."""
A_SUBJECTS = ("tajik", "math", "geography", "english", "biology",
              "chemistry", "physics", "history", "law", "literature")
B_SUBJECTS = ("tajik", "b_math", "b_physics", "b_geography", "b_literature",
              "b_english", "b_history", "b_biology", "b_chemistry")
ALL_SUBJECTS = A_SUBJECTS + tuple(s for s in B_SUBJECTS if s not in A_SUBJECTS)
CLUSTERS = {
    "A": [
        ["tajik", "math", "chemistry", "physics"],
        ["tajik", "math", "geography", "english"],
        ["tajik", "history", "literature", "english"],
        ["tajik", "history", "law", "english"],
        ["tajik", "biology", "chemistry", "physics"],
    ],
    "B": [
        ["tajik", "b_math", "b_physics"],
        ["tajik", "b_math", "b_geography"],
        ["tajik", "b_literature", "b_english"],
        ["tajik", "b_history", "b_english"],
        ["tajik", "b_biology", "b_chemistry"],
    ],
}
COMPONENTS = [{"id": cid, "grade": grade,
               "clusters": [{"id": i, "subjects": ids} for i, ids in enumerate(CLUSTERS[cid], 1)]}
              for cid, grade in (("A", 11), ("B", 9))]
