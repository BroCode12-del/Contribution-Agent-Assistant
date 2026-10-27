from io import StringIO

import pandas as pd


# AI-written reference solution, not an independent learner attempt.
def load_players(csv_text):
    return pd.read_csv(StringIO(csv_text), dtype={"player_id": str})
