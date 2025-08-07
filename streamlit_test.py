import streamlit as st 
import pandas as pd
from pymongo import MongoClient 
import redis 
import uuid
from typing import Dict, Any, List

# Neo4j imports
from neo4j import GraphDatabase  

# --- Data access classes ----------------------------------

class ProductStore:
    def __init__(
        self,
        mongo_uri: str = "mongodb://localhost:27017/",
        db_name: str = "eCommerce",
        collection_name: str = "products"
    ):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.products = self.db[collection_name]
        self.orders = self.db["orders"]

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.products.find({}, {"_id": 0}))

    def save_order(self, order: Dict[str, Any]):
        self.orders.insert_one(order)

    def close(self):
        self.client.close()


class Cart:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "cart"
    ):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.ns = namespace

    def _key(self, cart_id: str) -> str:
        return f"{self.ns}:{cart_id}"

    def add_item(self, cart_id: str, product_name: str, qty: int = 1):
        key = self._key(cart_id)
        self.r.hincrby(key, product_name, qty)

    def get_items(self, cart_id: str) -> Dict[str, int]:
        return self.r.hgetall(self._key(cart_id))

    def clear(self, cart_id: str):
        self.r.delete(self._key(cart_id))


# --- Neo4j Recommendation Engine --------------------------

class Recommender:
    def __init__(
        self,
        uri: str = "neo4j://localhost:7687",
        user: str = "neo4j",
        password: str = "12345678",
        database: str = "neo4j"
    ):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def recommend(self, cart_items: List[str], limit: int = 5) -> List[str]:
        """
        For each product in cart_items, find other products that
        users also purchased, aggregate counts, and return top N.
        """
        query = """
        UNWIND $cart AS itemName
        MATCH (u:User)-[:PURCHASED]->(p:Product {name: itemName})
        MATCH (u)-[:PURCHASED]->(rec:Product)
        WHERE NOT rec.name IN $cart
        RETURN rec.name AS name, count(*) AS freq
        ORDER BY freq DESC
        LIMIT $limit
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, cart=cart_items, limit=limit)
            return [record["name"] for record in result]  # :contentReference[oaicite:4]{index=4}


# --- Streamlit UI ----------------------------------------

@st.cache_data
def load_products() -> pd.DataFrame:
    store = ProductStore()
    df = pd.DataFrame(store.get_all())
    store.close()
    return df

def main():
    st.set_page_config(page_title="Mini E‑Commerce Store", layout="wide")
    st.title("🛒 Mini E‑Commerce Store")

    # Initialize session cart_id
    if "cart_id" not in st.session_state:
        st.session_state.cart_id = str(uuid.uuid4())

    cart = Cart()
    store = ProductStore()
    df = load_products()

    # Sidebar: filters & cart
    st.sidebar.header("Filters")
    cats = ["All"] + sorted(df["Category"].unique())
    choice = st.sidebar.selectbox("Category", cats)
    filtered = df if choice == "All" else df[df["Category"] == choice]

    st.sidebar.markdown("---")
    st.sidebar.header("🛍️ Your Cart")
    items = cart.get_items(st.session_state.cart_id)
    if items:
        total = 0.0
        for name, qty in items.items():
            price = float(df.loc[df["Product Name"] == name, "Price"].iloc[0])
            line = price * int(qty)
            total += line
            st.sidebar.write(f"{name} × {qty} = ${line:,.2f}")
        st.sidebar.markdown(f"**Total: ${total:,.2f}**")

        # Show recommendations
        rec_engine = Recommender(password="12345678")
        recs = rec_engine.recommend(list(items.keys()))
        rec_engine.close()
        if recs:
            st.sidebar.markdown("**You might also like:**")
            for r in recs:
                st.sidebar.write(f"• {r}")

        if st.sidebar.button("Checkout"):
            order = {
                "order_id": str(uuid.uuid4()),
                "cart_id": st.session_state.cart_id,
                "items": [
                    {
                        "name": name,
                        "quantity": int(qty),
                        "unit_price": float(df.loc[df["Product Name"] == name, "Price"].iloc[0])
                    }
                    for name, qty in items.items()
                ],
                "total": total,
                "status": "confirmed"
            }
            store.save_order(order)
            cart.clear(st.session_state.cart_id)
            st.sidebar.success("✅ Purchase confirmed!")
    else:
        st.sidebar.write("_(empty)_")

    # Main product listing
    st.subheader(f"Products ({len(filtered)})")
    for _, row in filtered.iterrows():
        cols = st.columns([3,1])
        with cols[0]:
            st.markdown(f"**{row['Product Name']}**")
            st.write(f"Category: {row['Category']}")
            st.write(f"Price: ${row['Price']}")
            st.write(f"Stock: {row['Quantity Available']}")
        with cols[1]:
            if st.button("Add to Cart", key=row["Product Name"]):
                cart.add_item(st.session_state.cart_id, row["Product Name"])
                st.toast(f"Added {row['Product Name']}")

    store.close()

if __name__ == "__main__":
    main()
