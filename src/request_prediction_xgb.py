#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""movie_lens_xgboost.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1NHjxVgCICcp_H6V4Wi63ygqiKiM0moGH

# Import libraries
"""

import pandas as pd
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import datetime
import numpy as np
np.random.seed(13)

n_input_cols = 22
n_output_cols = 1

def prepare_data(ratings_file, movies_file):
    """# Load data"""

    rating_data = pd.read_csv(ratings_file, index_col='timestamp', parse_dates=['timestamp'], date_parser = lambda x: datetime.datetime.fromtimestamp(int(x)))
    movie_data = pd.read_csv(movies_file, index_col='movieId')

    """## Process data
    **Assumption**: one rating = one request
    """

    del rating_data['userId']
    rating_data.head()

    del movie_data['title']
    movie_data.head()

    def assign_class(n_req, total_req):
        """
        assign class based on the no. of request received
        """
        
        # top 1% of the day are Class 1
        if n_req > 0.01 * total_req:
            return 1
        # top 0.5% of the day are Class 2
        elif n_req > 0.005 * total_req:
            return 2
        # top 0.01% of the day are Class 3
        elif n_req > 0.001 * total_req:
            return 3
        # rest are Class 4
        else:
            return 4

    def group_movies(daywise_group):
        """
        add request probablity to input pandas DataFrame
        
        :param daywise_group: a DataFrame containing movieId and corresponding ratings for a single day.
        """

        df = daywise_group.groupby("movieId").count()   
        # `rating` column now holds the no. of requests, so rename the column to avoid confusion
        df.rename(columns={"rating":"req"}, inplace=True)
        df['totalReq'] = daywise_group.shape[0]
        # request probablity for that day
        df['reqProb'] = daywise_group.groupby("movieId").count()['rating'] / df['totalReq']
        return df

    grouped_by_movie = rating_data.resample("1y").apply(group_movies)
    # grouped_by_movie['class'] = grouped_by_movie[['req', 'totalReq']].apply(lambda x:assign_class(x['req'], x['totalReq']), axis=1)
    grouped_by_movie.reset_index(level='movieId', inplace=True)
    grouped_by_movie.head()

    grouped_by_movie.pivot(columns='movieId', values='req').fillna(0).iloc[:100,:5].plot()

    """### Add genres"""

    grouped_by_movie = pd.merge(grouped_by_movie.reset_index(), movie_data.reset_index())
    grouped_by_movie.set_index('timestamp', inplace = True)
    grouped_by_movie.head()

    # Convert genres(str) to a binary matrix
    # because string are good for humans but
    # machines like numbers!
    from sklearn.preprocessing import MultiLabelBinarizer
    splitted = grouped_by_movie['genres'].apply(lambda x:x.split("|"))
    mlb = MultiLabelBinarizer()
    genre_matrix = mlb.fit_transform(splitted)

    genre_df = pd.DataFrame(genre_matrix)

    with_genre = pd.merge(grouped_by_movie.reset_index(), genre_df.reset_index(), left_index=True, right_index=True)
    del with_genre['genres'], with_genre['index']

    # shift class column to the end
    with_genre = with_genre[ list(filter(lambda x: x!='req', with_genre.columns)) + ['req']]

    with_genre.set_index('timestamp', inplace = True)
    with_genre.head()

    # We are selecting a single movie here, selecting 
    # multiple movies will yield bad results because 
    # of difference in data points.
    movie_history = with_genre.copy()
    movie_history = movie_history.reset_index().sort_values(['movieId','timestamp'])
    movie_history['Y'] = np.roll(movie_history['req'], -1)
    movie_history.set_index('timestamp', inplace=True)
    # movie_history.pivot(columns='movieId', values='req').plot(kind='bar', title="Request Counts/day")
    del movie_history['totalReq']
    del movie_history['movieId']
    movie_history.head()

    mlb.classes_

    """# Crunching numbers!"""

    from sklearn.preprocessing import MinMaxScaler
    from sklearn.compose import ColumnTransformer, make_column_transformer

    values = movie_history.values
    # #print(values)
    # one_hot_encoded = np.concatenate((list(map(lambda x:np.eye(4)[x-1], values[:,23].astype('int')) ),
    #                list(map(lambda x:np.eye(4)[x-1], values[:,24].astype('int')))), axis=1)
    # values = np.concatenate((movie_history.values[:,:23], one_hot_encoded), axis=1)

    # Scale 
    scaler = MinMaxScaler()
    scaled_values = scaler.fit_transform(values)
    scaled_values.shape

    """## Make X and Y"""

    X = scaled_values[:,:n_input_cols]
    y = scaled_values[:,n_input_cols:]
    # reshape
    # X = X.reshape(X.shape[0], 1, n_input_cols)
    # y = y.reshape(y.shape[0], 1, n_output_cols)
    print(X.shape)
    print(y.shape)

    """## train_test_split"""

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, shuffle=False)

    """# Make Model"""

    from xgboost import XGBRegressor

    model = XGBRegressor()
    model.fit(X, y)

    prediction = model.predict(X_test)
    from sklearn.metrics import mean_squared_error
    print("mse on testing data: {}".format(mean_squared_error(prediction, y_test)))
    return mlb, scaler, model

def predict(model, scaler, input_array):
    dat = np.concatenate((input_array, [[0]*n_output_cols]*input_array.shape[0]), axis=1)
    dat = scaler.transform(dat)[:,:n_input_cols]
    predicted = model.predict(dat)

    predicted = predicted.reshape(1,n_output_cols)
    x = np.concatenate(([[0]*n_input_cols]*input_array.shape[0], predicted), axis=1)
    return scaler.inverse_transform(x)[:,n_input_cols:]
