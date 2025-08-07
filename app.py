import redis
import shlex
from pymongo import MongoClient
from bson import ObjectId
import json
from datetime import datetime
import gradio as gr
from neo4j import GraphDatabase

r = redis.Redis(decode_responses=True)

# connect to mongo db running on localhost
client = MongoClient("mongodb://localhost:27017/") 
db = client["eCommerce"]

def add_item_to_cart(item_name, db, r) -> str:
    # Fetch the product from MongoDB by product name
    product = db.products.find_one({"Product Name": item_name})

    # If the product is not found, return an error message
    if not product:
        return "Product not found"

    # Convert the product's ObjectId to a string
    product_id = str(product.get("_id"))

    # Retrieve all items currently in the cart from Redis
    cart_items = r.lrange("cart", 0, -1)

    # Get the available stock quantity for the product
    stock_quantity = product.get("Quantity Available")

    # Iterate through items in the cart to check if this product is already there
    for index, item in enumerate(cart_items):        
        item_data = json.loads(item)

        # Get the quantity of the product already in the cart (default is 1 if not found)
        qty_cart = item_data.get("Quantity in Cart", 1)

        # If the product is already in the cart
        if item_data["_id"] == product_id:
            # Check if there's enough stock to add one more
            if (stock_quantity - qty_cart - 1 >= 0):
                # Enough stock available: increase quantity in cart
                item_data["Quantity in Cart"] += 1
                r.lset("cart", index, json.dumps(item_data))
                return "Added item to cart"
            else:
                # Not enough stock to add more of this item
                return "Unable to add another item - out of stock"

    # If item is not yet in the cart, attempt to add it with quantity = 1
    if (stock_quantity - 1 >= 0):
        cart_item = {
            "_id": product_id,
            "ID": product["ID"], 
            "Quantity in Cart": 1,            
            # "Quantity Available": product["Quantity Available"],  
            "Product Name": product["Product Name"],
            "Price": product["Price"],
            "Category": product["Category"]               
        }

        # Add the item to the cart as a new entry
        r.rpush("cart", json.dumps(cart_item))
        return "Added item to cart"
    else:
        # Not enough stock to even add the item once
        return "Unable to add another item - out of stock"

def remove_item_from_cart(item_name, db, r) -> str:
    product = db.products.find_one({"Product Name":item_name})
    product_id = str(product.get("_id"))
    
    # get items from redis
    cart_items = r.lrange("cart", 0, -1)
    # check if items are already in the cart
    for index, item in enumerate(cart_items):
        item_data = json.loads(item)
        if item_data["_id"] == product_id:
            # Item is already in cart, increase quantity
            item_data["Quantity in Cart"] -= 1
            if item_data["Quantity in Cart"] <= 0:
                # Remove item completely from cart if quantity is zero or less
                r.lrem("cart", 1, item)
                return f"Removed '{item_name}' from cart."
            else:
                # Update item with new quantity
                r.lset("cart", index, json.dumps(item_data))
                return f"Decreased quantity of '{item_name}' in cart."

def checkout(db, r):
    # List to hold names of items that are out of stock
    out_of_stock_items = []

    # Retrieve all cart items from Redis
    cart_items = r.lrange("cart", 0, -1)

    # Process each item in the cart
    for cart_item_json in cart_items:
        # Parse JSON string to Python dictionary
        cart_item = json.loads(cart_item_json)
        product_id = cart_item["_id"]
        qty = cart_item.get("Quantity in Cart", 1)
        price = cart_item.get("Price")
        product_name = cart_item["Product Name"]

        # Fetch the product from the MongoDB database by its ObjectId
        product = db.products.find_one({"_id": ObjectId(product_id)})
        quantity_stock = product.get("Quantity Available")

        # If enough stock is available
        if (quantity_stock - qty >= 0):
            # Reduce the stock quantity in the database
            quantity_stock = quantity_stock - qty
            product["Quantity Available"] = quantity_stock

            # Update the product stock in MongoDB
            db.products.update_one(
                {"_id": product["_id"]},
                {"$set": {"Quantity Available": quantity_stock}}
            )

            # Prepare the purchase entry to insert into the 'purchases' collection
            purchased_product = {
                "Product Name": product["Product Name"],
                "Price": product["Price"],
                "Quantity": qty,
                "Total": price * qty,
                "Category": product["Category"],
                "Date": datetime.now()
            }

            # Insert the purchase into the database
            db.purchases.insert_one(purchased_product)

            # Remove the item from the Redis cart
            r.lrem("cart", 1, cart_item_json)
        else:
            # If not enough stock, add item name to out-of-stock list
            out_of_stock_items.append(product_name)

    # If any items couldn't be purchased due to insufficient stock
    if len(out_of_stock_items) > 0:
        return f"The following items could not be purchased, because we're out of stock: {', '.join(out_of_stock_items)}"
    else:
        return "Purchase successful"

def view_cart(db, r):
    # Retrieve all cart items stored in Redis list "cart"
    cart_items = r.lrange("cart", 0, -1)

    # If the cart is empty, return a friendly message
    if not cart_items:
        return "🛒 Your cart is empty."

    # Initialize a list to store formatted cart item strings
    item_names = []

    # Iterate through each item JSON string in the cart
    for cart_item_json in cart_items:
        try:
            # Convert JSON string to a Python dictionary
            cart_item = json.loads(cart_item_json)
            
            # Get the product name
            product_name = cart_item["Product Name"]

            # If product name exists, format the display string
            if product_name:
                qty = cart_item.get("Quantity in Cart", 1)  # Default quantity to 1 if missing
                price = cart_item.get("Price")              # Price of the item

                # Append formatted string with product name, quantity, price, and total cost
                item_names.append(
                    f"{product_name} (Qty: {qty}, Price: {price}; Total: {price * qty})"
                )

        except Exception as e:
            # Handle any error in reading or parsing cart item (e.g., bad JSON)
            print(f"Error reading cart item: {e}")
            continue

    # Join all formatted item strings with newline characters for display
    return "\n".join(item_names)








neo4j_driver  = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "eCommerce"))

def add_and_recommend(item_name, db, r):
    message = add_item_to_cart(item_name, db=db, r=r)
    recommendations = get_recommendations(r)
    return message, recommendations
    
def get_cart_neo4j(r):
    # Retrieve all cart items stored in Redis list "cart"
    cart_items = r.lrange("cart", 0, -1)
    # Initialize a list to store formatted cart item strings
    item_names = []
    # Iterate through each item JSON string in the cart
    for cart_item_json in cart_items:        
        # Convert JSON string to a Python dictionary
        cart_item = json.loads(cart_item_json)
        item_names.append(cart_item["Product Name"])
    return item_names


def get_recommendations(r):
    cart_items = get_cart_neo4j(r)
    
    with neo4j_driver.session() as session:
        query = """
        UNWIND $cart_items AS item
        MATCH (p:Product {name: item})<-[:PURCHASED]-(u:User)-[:PURCHASED]->(rec:Product)
        WHERE NOT rec.name IN $cart_items
        RETURN rec.name AS recommendation, COUNT(*) AS freq
        ORDER BY freq DESC
        LIMIT 5
        """
        result = session.run(query, cart_items=cart_items)
        recommendations = [record["recommendation"] for record in result]
        return ", ".join(recommendations)
    



# Get a distinct list of product names from the database to populate the dropdown
products = db.products.distinct("Product Name")

# Define the Gradio Blocks interface
with gr.Blocks() as demo:
    # App title
    gr.Markdown("# 🛍️ Shopping App")

    # Row containing dropdown and action buttons
    with gr.Row():
        # Dropdown for selecting a product
        item_input = gr.Dropdown(choices=products, label="Select Product")
        
        # Button to add selected item to cart
        add_btn = gr.Button("Add to Cart")
        
        # Button to remove one unit of the selected item from cart
        del_btn = gr.Button("Remove from Cart")
        
        # Button to proceed with checkout
        checkout_btn = gr.Button("Checkout")

    # Textbox to display messages (e.g., "Added to cart", "Out of stock", etc.)
    output = gr.Textbox(label="Message")

    # Textbox to display recommendations
    recommendation_box = gr.Textbox(label="You Might Also Like")

    # When the "Add to Cart" button is clicked, call add_and_recommend with the selected item
    add_btn.click(
        fn=lambda item_name: add_and_recommend(item_name, db=db, r=r), #add_item_to_cart(item_name, db=db, r=r),
        inputs=item_input,
        outputs=[output, recommendation_box]
    )

    # When the "Remove from Cart" button is clicked, call remove_item_from_cart with the selected item and the get_recommendations
    del_btn.click(
        fn=lambda item_name: (
            remove_item_from_cart(item_name, db=db, r=r),
            get_recommendations(r)
        ),
        inputs=item_input,
        outputs=[output, recommendation_box]
    )


    # Button to view current cart contents
    view_btn = gr.Button("View Cart")

    # Textbox to display the cart contents
    cart_display = gr.Textbox(label="Your Cart")

    # When "View Cart" is clicked, call view_cart and show the result in the textbox
    view_btn.click(
        lambda: view_cart(db, r),
        outputs=cart_display
    )

    # When "Checkout" is clicked, process the cart and return the result message
    checkout_btn.click(
        fn=lambda: (
                checkout(db=db, r=r),
                "",
                "🛒 Your cart is empty."
        ),
        outputs=[output, recommendation_box, cart_display]
    )

# Launch the Gradio app
demo.launch()
