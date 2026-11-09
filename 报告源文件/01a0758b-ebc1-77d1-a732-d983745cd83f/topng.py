
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/RSI-EdgeVision_参赛参考资料.pdf")
print("pages:", len(pdf))
for i in range(len(pdf)):
    page = pdf[i]
    img = page.render(scale=1.35).to_pil()
    img.save(r"C:/Users/LDP/.codex/visualizations/2026/09/06/01a0758b-ebc1-77d1-a732-d983745cd83f/pg%02d.png" % (i+1))
    print("pg%02d" % (i+1), img.size)
