from bs4 import BeautifulSoup
import re
import json
import pandas as pd

def clean_html_to_md_like(text: str) -> str:
    """
    将 HTML + MD 混合文本，清洗为 MD 语义文本
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    soup = BeautifulSoup(text, "html.parser")
    raw = soup.get_text(separator="\n")

    # 清理多余空行
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    return raw.strip()

def extract_md_section(text: str, section_title: str) -> str:
    """
    从 Markdown 语义文本中提取指定 section
    例如: section_title = "Description" / "Evaluation"
    """
    if not text:
        return ""

    lines = text.splitlines()
    result = []
    in_section = False

    section_header = f"# {section_title}".lower()

    for line in lines:
        stripped = line.strip()

        # 命中目标 section
        if stripped.lower() == section_header:
            in_section = True
            continue

        # 碰到下一个一级标题 or 分隔线，结束
        if in_section and (
            stripped.startswith("# ")
            or stripped.startswith("---")
        ):
            break

        if in_section:
            result.append(line)

    return "\n".join(result).strip()

def process_dataset_description(text: str) -> str:
    return clean_html_to_md_like(text)



def competitions_df_to_jsonl_v2(df, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            overview_md = clean_html_to_md_like(row["Overview"])

            record = {
                "CompetitionID": row["Id"],
                "Title": row["Title"],
                "SubTitle": row["Subtitle"],
                "Slug": row["Slug"],
                "HasLeaderboard": row["HasLeaderboard"],
                "DatasetDescription": process_dataset_description(
                    row["DatasetDescription"]
                ),
                "Description": extract_md_section(
                    overview_md, "Description"
                ),
                "Evaluation": extract_md_section(
                    overview_md, "Evaluation"
                ),
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    
    df = pd.read_csv("test_competitions.csv")
    competitions_df_to_jsonl_v2(df, "competitions_without_lrdbd.jsonl")