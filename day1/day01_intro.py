def main():
    # Project card variables
    product_name = "GSTSaral"
    target_user = "Small business owners, MSMEs, and freelancers in India"
    problem = "Understanding GST slabs, registration thresholds, and filing rules without complex legal jargon."
    data_source = "Official CBIC notifications, GST Council rate schedules, and CGST Act FAQs"

    # Print the project card using f-strings
    print("=" * 60)
    print(f"PROJECT CARD: {product_name}")
    print("=" * 60)
    print(f"Product     : {product_name}")
    print(f"Target User : {target_user}")
    print(f"Problem     : {problem}")
    print(f"Data Source : {data_source}")
    print("=" * 60)

    # Interactive user input
    user_name = input("\nEnter your name: ").strip()
    user_question = input(f"Hi {user_name}, what is your GST question today? ").strip()

    print("\n--- Summary ---")
    print(f"User     : {user_name}")
    print(f"Question : '{user_question}'")
    print(f"Thank you, {user_name}! {product_name} has logged your query.")


if __name__ == "__main__":
    main()
