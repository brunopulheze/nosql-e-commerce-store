def init_products_database():

    # Load CSV
    df = pd.read_csv("products.csv")

    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client["eCommerce"]
    collection = db["products"]

    # remove previous content
    collection.drop()

    # Insert data
    data = df.to_dict(orient="records")
    collection.insert_many(data)

init_products_database()