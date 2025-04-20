py -3.11 -m venv venv
call .\venv\Scripts\activate
pip install spacy==3.7.2
python -m spacy download ru_core_news_sm
pip install -r .\requirements.txt
mkdir configs
(
    echo API_ID=
    echo API_HASH=
    echo NOVITA_API_KEY=
) > configs\.env
pause