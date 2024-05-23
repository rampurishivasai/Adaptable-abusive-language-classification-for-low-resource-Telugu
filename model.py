import fasttext
import fasttext.util
from googletrans import Translator
from indicnlp.tokenize import indic_tokenize
import pickle
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

ft = fasttext.load_model('indicnlp.ft.te.300.bin')
ft.get_dimension()

fasttext.util.reduce_model(ft, 50)
ft.get_dimension()

def load_svm_model(model_filename):
    with open(model_filename, 'rb') as f:
        model = pickle.load(f)
    return model

def tokenize_telugu(text):
    return indic_tokenize.trivial_tokenize(text)

def get_sentence_vector(tokens, model):
    vectors = [model.get_word_vector(word) for word in tokens]
    return sum(vectors) / len(vectors) if vectors else None

def english_to_telugu_transliteration(text):
    translator = Translator()
    transliteration_result = translator.translate(text, src='auto', dest='te').text
    return transliteration_result

def classify_text(text, classifier_model):
    telugu_transliteration = english_to_telugu_transliteration(text)
    text_tokens = tokenize_telugu(telugu_transliteration)
    text_embedding = get_sentence_vector(text_tokens, ft)

    print('Transliterated text:',telugu_transliteration)
    print("Tokens:", text_tokens)
    # print("Text Embedding:", text_embedding)

    if text_embedding is not None:
        prediction = classifier_model.predict([text_embedding])
        if prediction==0 : return 0
        return 1
    else:
        return "Unable to generate text embedding."

# text = "puku lo sulli petti dengutha"
# result = classify_text(text, load_svm_model('model.pkl'))
# print("Abusive" if result == 0 else "Not Abusive")