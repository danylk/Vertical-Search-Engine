import os
from flask import Flask, render_template, request
from es_client import get_client, INDEX_NAME

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QREL_DIR = os.path.join(BASE_DIR, '..', 'results', 'qrels')

documents = []
queries = ["black lives matter", "women right", "racial justice", "disability right"]

# Pool of document IDs (URLs) to assess: 200 per query, in query order
with open(os.path.join(BASE_DIR, 'documents.txt'), 'r') as file:
   lines = file.readlines()
   for line in lines:
      documents.append(line.strip())

es = get_client()

app = Flask(__name__)

@app.route('/')
def index():
   return render_template('index.html')

@app.route('/assessment',methods = ['POST', 'GET'])
def result():
   if request.method == 'POST':
      result = request.form
      queryID = result.get('queryID')
      query = queries[int(queryID)]
      assessorID = result.get('assessorID')
      docNum = result.get('docNum')
      docID = documents[int(docNum)]

      # Record the grade in QREL format: <queryID> <assessorID> <docID> <grade>
      if result.get("grade"):
         grade = result.get("grade")
         score = "{} {} {} {}\n".format(queryID, assessorID, docID, grade)
         print(score)
         with open(os.path.join(QREL_DIR, 'QREL_{}.txt'.format(assessorID)), 'a') as f:
            f.write(score)
         docNum = str(int(docNum) + 1)
         docID = documents[int(docNum)]

      content = es.get(index=INDEX_NAME, id=docID)['_source']['content'].get('text')
      return render_template('assessment.html', queryID=queryID, query=query, assessorID=assessorID, docNum=docNum, docID=docID, content=content)

if __name__ == '__main__':
   app.run()
