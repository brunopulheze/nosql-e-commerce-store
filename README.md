## Project Overview

This project is a NoSQL e-commerce store built using MongoDB, Redis, Neo4j and Gradio. It provides a platform for users to browse products, manage their shopping cart, and view product recommendations based on their preferences.

## Features
- **Product Browsing**: Users can view a list of products with details such as name, price, and description.
- **Shopping Cart Management**: Users can add products to their cart, view the cart contents, and remove items.
- **Product Recommendations**: The system provides personalized product recommendations based on user preferences and browsing history.
- **User Interface**: A simple and intuitive interface built with Gradio for easy interaction.

## Technologies Used
- **MongoDB**: For storing product information and user data.
- **Redis**: For caching product data and managing session state.
- **Neo4j**: For managing product relationships and generating recommendations.
- **Gradio**: For building the user interface and enabling user interactions.

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```bash
   cd nosql-e-commerce-store
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Initialize the database:
   ```
   python init_products_db.py
   ```
5. Start the application:
   ```bash
   python app.py
   ```

## Usage
- Open your web browser and navigate to `http://localhost:7860` to access the application.
- Browse products, manage your shopping cart, and view recommendations.
