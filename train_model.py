# -*- coding: utf-8 -*-
# سكربت تدريب نموذج المطابقة باستخدام arabic-sts من Hugging Face

import os

def main():
    try:
        from datasets import load_dataset
        from sentence_transformers import SentenceTransformer, InputExample, losses
        from torch.utils.data import DataLoader
    except ImportError as e:
        print('تثبيت المتطلبات: pip install datasets sentence-transformers torch')
        raise e

    print('جاري تحميل مجموعة arabic-sts من Hugging Face...')
    ds = load_dataset('MohamedRashad/arabic-sts', trust_remote_code=True)

    print('جاري تحميل النموذج الأساسي...')
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

    train_data = ds['train']
    examples = []
    for row in train_data:
        s1 = (row.get('sentence1') or '').strip()
        s2 = (row.get('sentence2') or '').strip()
        score = float(row.get('similarity_score', 0))
        if not s1 or not s2:
            continue
        label = min(1.0, max(0.0, score / 5.0))
        examples.append(InputExample(texts=[s1, s2], label=label))

    if not examples:
        print('لم يتم العثور على بيانات صالحة. تحقق من أعمدة المجموعة.')
        return

    print(f'عدد الأمثلة: {len(examples)}')
    train_dataloader = DataLoader(examples, shuffle=True, batch_size=16)

    train_loss = losses.CosineSimilarityLoss(model)

    output_dir = 'tawun-match-model'
    print(f'بدء التدريب... الحفظ في: {output_dir}')
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=3,
        warmup_steps=100,
        output_path=output_dir
    )
    print('تم التدريب بنجاح.')

if __name__ == '__main__':
    main()
