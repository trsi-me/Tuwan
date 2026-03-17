# -*- coding: utf-8 -*-

_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            import os
            trained = os.path.join(os.path.dirname(__file__), 'tawun-match-model')
            if os.path.isdir(trained):
                _model = SentenceTransformer(trained)
            else:
                _model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        except Exception:
            _model = False
    return _model if _model else None

def _student_text(student):
    parts = [
        student.get('major') or '',
        student.get('skills') or '',
        student.get('department') or '',
    ]
    return ' '.join(p for p in parts if p).strip() or 'طالب'

def _company_text(company):
    parts = [
        company.get('ministry') or '',
        company.get('organization_category') or '',
        company.get('department') or '',
        company.get('name') or '',
    ]
    return ' '.join(p for p in parts if p).strip() or 'جهة'

def _embedding_match(student, companies):
    try:
        import numpy as np
        model = _get_model()
        if model is None:
            return None
        student_text = _student_text(student)
        student_emb = model.encode([student_text], convert_to_tensor=False)[0]
        comp_texts = [_company_text(c) for c in companies]
        comp_embs = model.encode(comp_texts, convert_to_tensor=False)
        scores = []
        for i, comp_emb in enumerate(comp_embs):
            sim = np.dot(student_emb, comp_emb) / (np.linalg.norm(student_emb) * np.linalg.norm(comp_emb) + 1e-9)
            score = int((sim + 1) * 50)
            score = max(0, min(100, score))
            reason = 'مطابقة دلالية بناءً على تشابه المعنى بين التخصص والجهة'
            scores.append((score, reason))
        return scores
    except Exception:
        return None

def _rule_based_score(student, company):
    from constants import MAJOR_TO_MINISTRY_KEYWORDS
    major = (student.get('major') or '').strip()
    skills = (student.get('skills') or '').strip()
    dept = (student.get('department') or '').strip()
    ministry = (company.get('ministry') or '').strip()
    comp_dept = (company.get('department') or '').strip()
    comp_cat = (company.get('organization_category') or '').strip()
    comp_text = f"{ministry} {comp_dept} {comp_cat}".lower()
    score = 0
    for m, keywords in MAJOR_TO_MINISTRY_KEYWORDS.items():
        if m in major or major in m:
            for kw in keywords:
                if kw in comp_text:
                    score += 15
                    break
            break
    if comp_dept and (comp_dept in major or major in comp_dept or comp_dept in dept):
        score += 20
    for kw in ['تقنية', 'حاسب', 'برمجة', 'برمجيات', 'معلومات', 'شبكات']:
        if kw in skills.lower() or kw in major.lower():
            if any(k in comp_text for k in ['اتصالات', 'تقنية', 'حاسب']):
                score += 15
                break
    return min(100, score), 'مطابقة بناءً على القواعد'

def match_student_to_companies_ai(student, companies):
    if not student:
        return []
    companies_list = [dict(c) for c in companies]
    scores_list = _embedding_match(student, companies_list)
    matched = []
    for i, comp in enumerate(companies_list):
        if scores_list and i < len(scores_list):
            score, reason = scores_list[i]
        else:
            score, reason = _rule_based_score(student, comp)
        if score >= 40:
            comp['match_score'] = score
            comp['match_reason'] = reason
            matched.append(comp)
    return sorted(matched, key=lambda x: x.get('match_score', 0), reverse=True)
