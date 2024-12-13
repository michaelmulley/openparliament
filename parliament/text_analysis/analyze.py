from parliament.text_analysis.corpora import load_background_model
from parliament.text_analysis.frequencymodel import FrequencyModel, STOPWORDS

def analyze_statements(statements, corpus_name, min_ratio=2):
    results = []
    ngram_lengths = [
        {
            'length': 3,
            # 'max_count': 3,
        },
        {
            'length': 2,
            # 'max_count': 8,
        },
        {
            'length': 1,
            # 'max_count': 20,
        }
    ]
    if sum(s.wordcount for s in statements) < 1000:
        return None
    seen = set(STOPWORDS)
    for opts in ngram_lengths:
        bg = load_background_model(corpus_name, opts['length'])
        model = FrequencyModel.from_statement_qs(
            statements, opts['length']).diff(bg, min_ratio=min_ratio)
        top = iter(model.most_common(50))
        count = 0
        for item in top:
            # if count >= opts['max_count']:
            #     continue
            words = item[0].split(' ')
            #if sum(word in seen for word in words) / float(len(words)) < 0.6:
            if words[0] not in seen and words[-1] not in seen:
                seen.update(words)
                results.append({
                    "text": item[0],
                    "score": item[1] * 1000
                    #"size": _log_scale(item[1], opts['range'])
                })
                count += 1
    #results.sort(key=lambda r: r['size'], reverse=True)
    return results
