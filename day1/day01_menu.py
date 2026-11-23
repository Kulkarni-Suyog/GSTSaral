def show_about():
    print("\n--- About GSTSaral ---")
    print("GSTSaral simplifies Indian Goods and Services Tax (GST) rules,")
    print("helping MSMEs and freelancers quickly check tax slabs and compliance thresholds.")


def show_sample_questions():
    print("\n--- Sample GST Questions ---")
    print("1. What is the GST rate on handcrafted leather footwear?")
    print("2. When is GST registration mandatory for a service provider?")
    print("3. What is the due date for filing GSTR-3B?")


def check_gst_registration_rule():
    print("\n--- GST Registration Threshold Check ---")
    business_type = input("Enter business type (goods / services): ").strip().lower()
    try:
        turnover = float(input("Enter your annual aggregate turnover (in INR Lakhs): ").strip())
    except ValueError:
        print("Invalid amount. Please enter a numeric value in Lakhs (e.g., 25).")
        return

    if business_type == "goods":
        if turnover > 40:
            print(f"Result: Mandatory GST registration required (Turnover {turnover}L exceeds ₹40 Lakhs limit).")
        elif turnover >= 20:
            print(f"Result: Exempt in most states (limit is ₹40L for goods), unless operating in special category states (₹20L limit).")
        else:
            print(f"Result: Exempt from mandatory GST registration (Below ₹20 Lakhs).")
    elif business_type == "services":
        if turnover > 20:
            print(f"Result: Mandatory GST registration required (Turnover {turnover}L exceeds ₹20 Lakhs limit).")
        elif turnover >= 10:
            print(f"Result: Exempt in normal states (limit is ₹20L), but mandatory in special category states (₹10L limit).")
        else:
            print(f"Result: Exempt from mandatory GST registration (Below ₹10 Lakhs).")
    else:
        print("Invalid business type. Please enter either 'goods' or 'services'.")


def main():
    while True:
        print("\n" + "=" * 35)
        print("         GSTSaral Main Menu        ")
        print("=" * 35)
        print("1. About GSTSaral")
        print("2. Sample Questions")
        print("3. Check GST Registration Rule")
        print("0. Exit")
        print("=" * 35)

        choice = input("Select an option (0-3): ").strip()

        if choice == "1":
            show_about()
        elif choice == "2":
            show_sample_questions()
        elif choice == "3":
            check_gst_registration_rule()
        elif choice == "0":
            print("Exiting GSTSaral. Goodbye!")
            break
        else:
            print("Invalid option. Please choose 0, 1, 2, or 3.")


if __name__ == "__main__":
    main()
