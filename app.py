from flask import Flask, render_template, request
import os
import fitz  # PyMuPDF
import re
from collections import Counter
import spacy
from spacy.matcher import Matcher

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def extract_text_from_pdf(pdf_file_path):
    try:
        pdf_document = fitz.open(pdf_file_path)
        text = ""
        for page in pdf_document:
            text += page.get_text()
        pdf_document.close()
        return text
    except Exception as e:
        print(f"Error while processing {pdf_file_path}: {e}")
        return ""

def preprocess_text(text):
    # Merge hyphenated words that are split across lines
    text = re.sub(r'-\n', '', text)
    return text

def highlight_matching_words(text, matching_words, highlight_styles=None):
    if not highlight_styles:
        # Default highlighting style (yellow background)
        highlight_styles = ['background-color: yellow;'] * len(matching_words)

    for word, highlight_style in zip(matching_words, highlight_styles):
        text = re.sub(
            rf'\b({re.escape(word)})\b',
            f'<span style="{highlight_style}">{word}</span>',
            text,
            flags=re.IGNORECASE
        )
    return text




def extract_words_with_occurrences_from_pdf(pdf_file_path, words_to_extract):
    article_text = extract_text_from_pdf(pdf_file_path).lower()  # Convert entire text to lowercase

    if not article_text:
        return Counter(), "", ""

    # Preprocess the article text to handle hyphenated words
    article_text = preprocess_text(article_text)

    # Load spaCy English language model
    nlp = spacy.load("en_core_web_sm")

    # Tokenize the article text
    doc = nlp(article_text)

    # Initialize the Matcher
    matcher = Matcher(nlp.vocab)

    # Prepare patterns for matching singular and plural forms of the words
    word_patterns = [[{"LOWER": word.lower()}] for word in words_to_extract]

    # Add word patterns to the Matcher
    matcher.add("WordsPatterns", word_patterns)

    # Find matches in the document
    matches = matcher(doc)

    # Count the occurrences of matched tokens
    word_counter = Counter()
    matching_words = set()
    for match_id, start, end in matches:
        matched_word = doc[start:end].text.lower()  # Convert matched word to lowercase
        word_counter[matched_word] += 1
        matching_words.add(matched_word)

    # Define different highlight styles for each matching word
    highlight_styles = [
        'background-color: yellow;',  # Style for the first word
        'background-color: pink;',    # Style for the second word
        'background-color: lightblue;',  # Style for the third word
        # Add more styles as needed
    ]

    # Highlight the matching words in the main content using the defined styles
    highlighted_text = highlight_matching_words(article_text, matching_words, highlight_styles)

    return word_counter, highlighted_text

def process_pdf_files(pdf_folder_path, words_to_extract):
    results = []
    pdf_files = [file for file in os.listdir(pdf_folder_path) if file.lower().endswith('.pdf')]
    for pdf_file in pdf_files:
        pdf_file_path = os.path.join(pdf_folder_path, pdf_file)
        word_occurrences, highlighted_text = extract_words_with_occurrences_from_pdf(pdf_file_path, words_to_extract)

        result = {
            'file_name': pdf_file,
            'word_occurrences': word_occurrences,
            'highlighted_text': highlighted_text,
        }

        results.append(result)

    return results


def delete_previous_uploads(upload_folder):
    for file in os.listdir(upload_folder):
        file_path = os.path.join(upload_folder, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error while deleting {file_path}: {e}")

def save_highlighted_text_to_html(highlighted_text, pdf_file_name, html_folder_path):
    html_file_path = os.path.join(html_folder_path, f'{pdf_file_name}_highlighted_text.html')
    with open(html_file_path, 'w', encoding='utf-8') as html_file:
        html_file.write('<!DOCTYPE html>\n<html>\n<head>\n<title>Highlighted Text</title>\n</head>\n<body>\n')
        html_file.write(highlighted_text)
        html_file.write('\n</body>\n</html>')
    return html_file_path

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Check if the 'uploads' directory exists; if not, create it.
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        # Delete previous uploads before processing new files
        delete_previous_uploads(app.config['UPLOAD_FOLDER'])

        # Check if a PDF file and a text file are uploaded
        if 'pdf_file' not in request.files or 'highlight_file' not in request.files:
            return render_template('index.html', error_message='Both PDF and text files are required.')

        pdf_file = request.files['pdf_file']
        highlight_file = request.files['highlight_file']

        # Check if the files have names and are allowed
        if pdf_file.filename == '' or highlight_file.filename == '':
            return render_template('index.html', error_message='No selected file.')

        if pdf_file and highlight_file:
            # Save the uploaded files to the 'uploads' directory
            pdf_file_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
            highlight_file_path = os.path.join(app.config['UPLOAD_FOLDER'], highlight_file.filename)

            pdf_file.save(pdf_file_path)
            highlight_file.save(highlight_file_path)

            # Read the highlighted words from the text file
            with open(highlight_file_path, 'r') as file:
                words_to_extract = file.read().split(',')

            # Process the PDF file and store the result in a list
            results = process_pdf_files(app.config['UPLOAD_FOLDER'], words_to_extract)

            # Save the highlighted text to HTML files and provide download links
            download_links = []
            for result in results:
                html_file_path = save_highlighted_text_to_html(result['highlighted_text'], result['file_name'], app.config['UPLOAD_FOLDER'])
                download_links.append(html_file_path)

            # Pass the list of results and the list of download links to the template
            return render_template('index.html', results=results, download_links=download_links)

    return render_template('index.html', error_message=None)


from flask import send_file


@app.route('/download_html')
def download_html():
    file_name = request.args.get('file', '')
    html_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{file_name}_highlighted_text.html')

    if os.path.isfile(html_file_path):
        return send_file(html_file_path, as_attachment=True)
    else:
        return "HTML File not found."

# ...

if __name__ == '__main__':
    app.run()
