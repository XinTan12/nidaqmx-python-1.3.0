import fitz
import sys
from pathlib import Path

def pdf_to_markdown(pdf_path):
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    md_text = []

    for i, page in enumerate(doc):
        # 提取纯文本
        text = page.get_text("text")
        # 去掉重复空行
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        text = "\n".join(lines)
        # 按页分段
        md_text.append(f"\n\n# Page {i+1}\n\n{text}")

    output_path = pdf_path.with_suffix(".md")
    output_path.write_text("\n".join(md_text), encoding="utf-8")

    print(f"\n✅ 转换完成！Markdown 文件已保存为:\n{output_path}\n")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n用法: python pdf_to_md.py 文件路径.pdf\n")
    else:
        pdf_to_markdown(sys.argv[1])
