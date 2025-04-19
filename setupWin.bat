Set-ExecutionPolicy RemoteSigned -Scope Process
py -3.11 -m venv venv
call .\venv\Scripts\activate
pip install spacy==3.7.2
python -m spacy download ru_core_news_sm
pip install -r .\requirements.txt
(
    echo API_ID=ваш_api_id
    echo API_HASH=ваш_api_hash
) > .env
pause