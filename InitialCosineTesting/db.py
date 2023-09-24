# pip install pandas openai scipy matplotlib plotly scikit-learn numpy pymongo
# needs openai.txt mongo.txt cnn.json fox.json in the same directory

import pandas as pd
import openai
from openai.embeddings_utils import cosine_similarity
from random import choice

with open('openai.txt', 'r') as f:
    openai.api_key = f.read()

class VectorDB():
    def __init__(self) -> None:
        self.left = pd.DataFrame(columns=['id', 'title', 'content', 'source', 'publishedAt', 'urlToImage', 'vector', 'closest_article_id'])
        self.right = pd.DataFrame(columns=['id', 'title', 'content', 'source', 'publishedAt', 'urlToImage', 'vector', 'closest_article_id'])

    def add_left(self, article):
        # get vector
        vector = self.get_vector(article['content'])
        # compare with all right articles and find id of article with highest similarity
        closest_article_id = None
        max_similarity = 0

        for i in range(len(self.right)):
            similarity = cosine_similarity(vector, self.right.iloc[i]['vector'])
            if similarity > max_similarity:
                max_similarity = similarity
                closest_article_id = self.right.iloc[i]['id']
        
        # add to left
        article['vector'] = vector
        article['closest_article_id'] = closest_article_id
        # update right
        if closest_article_id != None:
            self.right.loc[self.right['id'] == closest_article_id,'closest_article_id'] = article['id']

        self.left = pd.concat([self.left, pd.DataFrame(article)])

    def add_right(self, article):
        # get vector
        vector = self.get_vector(article['content'])
        # compare with all left articles and find id of article with highest similarity
        closest_article_id = None
        max_similarity = 0
        for i in range(len(self.left)):
            similarity = cosine_similarity(vector, self.left.iloc[i]['vector'])
            if similarity > max_similarity:
                max_similarity = similarity
                closest_article_id = self.left.iloc[i]['id']
        
        # update left
        if closest_article_id != None:
            self.left.loc[self.left['id'] == closest_article_id, 'closest_article_id'] = article['id']
        # add to right
        article['vector'] = vector
        article['closest_article_id'] = closest_article_id

        self.right = pd.concat([self.right, pd.DataFrame(article)])

    def get_vector(self, article):
        response = openai.Embedding.create(
            input=article,
            model="text-embedding-ada-002"
        )
        return [e['embedding'] for e in response['data']]
    
    def get_combined(self, article_id, side=None):
        if side == None:
            side = choice(['left', 'right'])

        if side == 'left':
            article = self.left[self.left['id'] == article_id]
            closest_article_id = int(article['closest_article_id'].iloc[0])
            closest_article = self.right[self.right['id'] == closest_article_id]
        elif side == 'right':
            article = self.right[self.right['id'] == article_id]
            closest_article_id = int(article['closest_article_id'].iloc[0])

            closest_article = self.left[self.left['id'] == closest_article_id]            

        prompt="Below are two articles covering the same topic, go through them and generate a new article body without the title combining them and covering both sides:\nArticle 1:\n{}\nArticle 2:\n{}\n\nArticle 3:\n".format(article['content'], closest_article['content'])


        new_content = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=prompt,
            max_tokens=512,
            temperature=0.7,
        )['choices'][0]['text']

        new_title = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"Suggest a good title for this article(return only a capitalised string without any quatation marks):\n {new_content}\n\n",
            max_tokens=50,
            temperature=0.7,
        )['choices'][0]['text']

        return {
            'title': new_title.replace('"', '').strip(),
            'content': new_content.strip(),
            'source': article['source'].iloc[0]+' and '+closest_article['source'].iloc[0],
            'publishedAt': article['publishedAt'].iloc[0],
            'urlToImage': str(choice([article['urlToImage'], closest_article['urlToImage']]).iloc[0]),
            'categories': self.get_categories(new_content)
        }
    
    def get_categories(self, text):
        # use text to generate comma separated list of categories

        response = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"Choose one tag for this article from these options only, you are not allowed to output any other tag(only output the tag as a sigle word and nothing else): politics, environment, finance, sports, technology, war\n\n {text}\n\n",
            max_tokens=2,
            temperature=0.5,
        )['choices'][0]['text']

        return [e.strip().lower() for e in response.strip().split(',')]
    
    def get_new_articles(self):
        # see which side has less articles
        if len(self.left) < len(self.right):
            side = 'left'
            db = self.left
        else:
            side = 'right'
            db = self.right

        # get new articles for all of these which have a closest article
        new_articles = []
        temp = db[db['closest_article_id'] != None]
        for i in range(len(temp)):
            try:
                article = temp.iloc[i]
                new_articles.append(self.get_combined(article['id'], side=side))
                print(new_articles[-1])
            except Exception as e:
                print(e)
                pass
        return new_articles

import json


# ExampleArticle:
# {'urlToImage': 'https://media.cnn.com/api/v1/images/stellar/prod/230923130522-jimmy-rosalynn-carter-file-2018.jpg?c=original',
#  'title': 'Jimmy and Rosalynn Carter visit Georgia festival ahead of former president’s 99th birthday, Carter Center says',
#  'content': 'Former President Jimmy Carter and his wife, Rosalynn, took a ride through the Plains Peanut Festival in Plains, Georgia, on Saturday, the Carter Center said in a social media post.  “Beautiful day for President & Mrs. Carter to enjoy a ride through the Plains Peanut Festival! And just a week before he turns 99. We’re betting peanut butter ice cream is on the menu for lunch! #JimmyCarter99,” the Carter Center said in a tweet sharing a video of the Carters riding in an SUV down a street lined with festival-goers. Jimmy Carter, who turns 99 on October 1, entered hospice care in February. The former president beat brain cancer in 2015 but faced a series of health scares in 2019, and consequentially underwent surgery to remove pressure on his brain. In an interview with People published last month, the Carters’ grandson said, “It’s clear we’re in the final chapter.” Family and caregivers had been the only recent visitors to the Carters’ Plains home, Josh Carter told People.  Josh Carter said his grandmother Rosalynn Carter, who has dementia, is cognizant of her diagnosis. “She still knows who we are, for the most part – that we are family,” he said. Jimmy and Rosalynn Carter have been married for 77 years and are the longest-married presidential couple. Jimmy Carter was born in Plains, Georgia, and grew up in the nearby community of Archery. A peanut farmer and Navy lieutenant before going into politics, the Democrat served one term as governor of Georgia and was president from 1977 to 1981.',
#  'source': 'CNN',
#  'publishedAt': '2023-09-23T18:51:26Z',
#  'id': -3059632832363739956}

def test(n=2):
    with open('cnn.json', 'r') as f:
        cnn_articles = json.load(f)

    with open('fox.json', 'r') as f:
        fox_articles = json.load(f)

    test_db = VectorDB()
    for article in cnn_articles[:n]:
        article['id'] = hash(article['title'])
        test_db.add_left(article)

    for article in fox_articles[:n]:
        article['id'] = hash(article['title'])
        test_db.add_right(article)

    return test_db.get_new_articles()


# with open("new.json", "w") as outfile:
#     outfile.write(json.dumps(test(200), indent=4))

data = test(200)

categs = []

for i in data:
    categs+=i['categories']

categs = list(set(categs))

categs_count = {e : 0 for e in categs}
for i in data:
    categs_count[i['categories'][0]]+=1

categs_count = {k: v for k, v in sorted(categs_count.items(), key=lambda item: item[1], reverse=True)}

top_categs = list(categs_count.keys())[:5]
data = [i for i in data if i['categories'][0] in top_categs]


new_format = []
for i in data:
    new_format.append(
        {
            "title": i['title'],
            "news_article": i['content'],
            "source": "CNN and Fox News",
            "date": '2023-09-22',
            "urlToImage": [i['urlToImage']],
            "hashtags": i['categories'][0]
        }
    )

# with open("new_format.json", "w") as outfile:
#     outfile.write(json.dumps(new_format, indent=4))


from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

with open('mongo.txt', 'r') as f:
    uri = f.read()

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
client["db"]["Articles"].insert_many(new_format)