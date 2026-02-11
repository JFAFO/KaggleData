import pandas as pd

if __name__ == "__main__":
    df = pd.read_csv("Competitions.csv")
    test_def = df.head(10)
    test_def.to_csv("test_competitions.csv", index=False)