filename = "backend/data/GOOG.csv"
with open(filename) as f:
    data = f.readlines()

data.reverse()

with open(filename, 'w') as f:
    f.writelines(data)