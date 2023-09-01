FROM python:3
ADD . .
RUN pip install -r requirements.txt
RUN sed -i 's/getargspec/getfullargspec/g' /usr/local/lib/python3.11/site-packages/parsimonious/expressions.py
CMD [ "python", "./main.py" ]