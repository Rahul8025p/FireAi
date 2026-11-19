"""
50 plain-language user descriptions for testing the NLP parser.
Each has: text, expected_fields, expected_clarification.
"""
from __future__ import annotations

PLAIN_LANGUAGE_INPUTS = [
    # 1. Complete English
    {
        "text": "I earn 15 lakhs per year. I live in Mumbai and pay 25,000 rent per month. My HRA is 5 lakhs annually. I invest 1.5 lakhs in 80C.",
        "expected_fields": {
            "salary": 1_500_000,
            "hra": 500_000,
            "rent": 300_000,
            "is_metro": True,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 2. Hinglish
    {
        "text": "Mera salary 12 lpa hai. Main Delhi mein rehta hoon aur 20000 per month rent deta hoon. 80C mein 1 lakh invest kiya hai.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": None,
            "rent": 240_000,
            "is_metro": True,
            "investment_80c": 100_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "What is your annual HRA from employer?",
    },

    # 3. Incomplete - missing salary
    {
        "text": "I invest 1.5 lakhs in PPF and ELSS every year. I also pay 20,000 per month rent in Bangalore.",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": 240_000,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "What is your annual gross salary?",
    },

    # 4. Contradictory city
    {
        "text": "I live in Pune which is a metro city and earn 10 lakhs per year.",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Pune is not a metro city for HRA purposes. Only Mumbai, Delhi, Chennai, and Kolkata qualify as metro. Is your city one of these?",
    },

    # 5. With senior parents
    {
        "text": "My annual salary is 18 LPA. I pay health insurance of 25,000 for myself and 50,000 for my parents who are both above 60 years old.",
        "expected_fields": {
            "salary": 1_800_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 50_000,
            "parents_senior_citizen": True,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 6. Home loan interest
    {
        "text": "I earn 20 lakhs per annum. I have a home loan and pay 1.8 lakhs in interest annually. No rent paid - I own the house.",
        "expected_fields": {
            "salary": 2_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 180_000,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 7. NPS contribution
    {
        "text": "Salary: 25 lakhs. I put 50,000 extra in NPS under 80CCD(1B) apart from my 1.5 lakh 80C investments.",
        "expected_fields": {
            "salary": 2_500_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 8. Everything complete
    {
        "text": "I am 35 years old, earning 20 LPA in Chennai. HRA is 6 lakhs, rent is 4 lakhs per year. I have done 1.5L 80C, 50k NPS, 25k medical for self, 50k for my 65-year old parents. Home loan interest is 2 lakhs.",
        "expected_fields": {
            "salary": 2_000_000,
            "hra": 600_000,
            "rent": 400_000,
            "is_metro": True,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 50_000,
            "parents_senior_citizen": True,
            "home_loan_interest": 200_000,
            "age": 35,
        },
        "expected_clarification": None,
    },

    # 9. Crore salary
    {
        "text": "My package is 1 crore per annum. No HRA, no deductions.",
        "expected_fields": {
            "salary": 10_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 10. Vague income description
    {
        "text": "I earn a decent salary and invest in mutual funds.",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "What is your annual gross salary?",
    },

    # 11. Monthly salary mentioned
    {
        "text": "My monthly salary is 1 lakh. I live in Kolkata and pay 15,000 rent per month.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": None,
            "rent": 180_000,
            "is_metro": True,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "What is your annual HRA from your employer?",
    },

    # 12. Hinglish + deductions
    {
        "text": "8 lakh salary hai, Hyderabad mein rehta hoon. 80C mein 80 hazaar kiya, aur parents ka medical insurance 20,000 hai.",
        "expected_fields": {
            "salary": 800_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 80_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": 20_000,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Are your parents senior citizens (60 or above)?",
    },

    # 13. Incomplete - HRA but no rent
    {
        "text": "I get 3 lakh HRA from my employer. My gross salary is 12 lakhs. I live in Bangalore.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": 300_000,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "How much rent do you pay annually?",
    },

    # 14. Age mentioned
    {
        "text": "I am 62 years old, retired from a PSU with a pension of 8 lakhs per year. I invest in senior citizen savings scheme.",
        "expected_fields": {
            "salary": 800_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": 62,
        },
        "expected_clarification": None,
    },

    # 15. Multiple deductions in brief text
    {
        "text": "12LPA, 80C=1.5L, 80D=25k, NPS=50k, home loan interest=1.8L",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": 25_000,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 180_000,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 16. English with lakhs written differently
    {
        "text": "My CTC is Rs 10,00,000 and I am based in New Delhi. HRA component is Rs 3,00,000. I pay Rs 25,000 monthly rent.",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": 300_000,
            "rent": 300_000,
            "is_metro": True,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 17. Contradictory: owns house + renting
    {
        "text": "I own my house in Gurgaon and also pay rent of 30,000 per month. My salary is 15 lakhs.",
        "expected_fields": {
            "salary": 1_500_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "You mentioned owning a house but also paying rent. Do you live in your own house (no HRA claim) or in a rented accommodation?",
    },

    # 18. Very brief
    {
        "text": "8 LPA",
        "expected_fields": {
            "salary": 800_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Could you share more details? For example: Do you receive HRA? Are you renting? What investments do you have (80C, NPS)?",
    },

    # 19. All zeros / no deductions stated
    {
        "text": "I earn 50 lakhs a year and have no deductions or investments.",
        "expected_fields": {
            "salary": 5_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 0,
            "investment_80ccd1b": 0,
            "medical_80d_self": 0,
            "medical_80d_parents": 0,
            "parents_senior_citizen": None,
            "home_loan_interest": 0,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 20. Hinglish with numbers in words
    {
        "text": "Mera paanch lakh salary hai. Koi investment nahi kiya. Age 28 hai.",
        "expected_fields": {
            "salary": 500_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": 28,
        },
        "expected_clarification": None,
    },

    # 21. 80D only, no salary
    {
        "text": "I pay 25,000 health insurance for myself and my wife. Parents are covered for 30,000 (they are senior citizens).",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 30_000,
            "parents_senior_citizen": True,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "What is your annual gross salary?",
    },

    # 22. High income, specific
    {
        "text": "I work at a startup. CTC is 2 crore. I have 80C of 1.5 lakhs, NPS 50k extra, home loan interest 2 lakhs. No HRA - I own my house in Bangalore.",
        "expected_fields": {
            "salary": 20_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 200_000,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 23. Missing rent amount
    {
        "text": "I live on rent in Mumbai and get HRA of 4 lakhs. Salary is 15 lakhs.",
        "expected_fields": {
            "salary": 1_500_000,
            "hra": 400_000,
            "rent": None,
            "is_metro": True,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "How much rent do you pay annually (or monthly)?",
    },

    # 24. English with abbreviations
    {
        "text": "Gross: 18L. HRA: 5L. Rent: 24k/month. Metro: yes (Bombay). 80C: 1.5L. 80D self: 25k. 80D parents: 50k (senior). Age: 40.",
        "expected_fields": {
            "salary": 1_800_000,
            "hra": 500_000,
            "rent": 288_000,
            "is_metro": True,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 50_000,
            "parents_senior_citizen": True,
            "home_loan_interest": None,
            "age": 40,
        },
        "expected_clarification": None,
    },

    # 25. Ambiguous rent period
    {
        "text": "I pay 20,000 rent in Pune. Salary 10 lakhs.",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Is the ₹20,000 rent monthly or annual? Also, do you receive HRA from your employer?",
    },

    # 26. Partial Hinglish with investment
    {
        "text": "Salary 10 lakh, PPF mein 1.5 lakh dala, aur ghar ke liye 2 lakh interest pay kiya.",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 200_000,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 27. With both old and new regime mention
    {
        "text": "I earn 20 LPA. Should I go for old or new tax regime? I have 80C of 1.5L and home loan interest of 2L.",
        "expected_fields": {
            "salary": 2_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 200_000,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 28. Contradictory 80C amount
    {
        "text": "I invest 2 lakhs in 80C. My salary is 12 lakhs.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 200_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 29. Formal language
    {
        "text": "My annual gross salary income from employment is INR 35,00,000. I reside in Mumbai on rent paying INR 40,000 per month. HRA received INR 10,00,000 per annum.",
        "expected_fields": {
            "salary": 3_500_000,
            "hra": 1_000_000,
            "rent": 480_000,
            "is_metro": True,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 30. Completely empty / irrelevant
    {
        "text": "What is the weather today?",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "I can help with income tax calculations. Could you tell me your annual salary and any deductions you have?",
    },

    # 31. HRA from employer, rent in home town (doesn't qualify)
    {
        "text": "I work in Hyderabad, get HRA of 2.4 lakhs, but actually live in my own house. I pay rent only for my parents' house in another city - 5000 per month.",
        "expected_fields": {
            "salary": None,
            "hra": 240_000,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "What is your annual salary? Also, do you personally pay rent for your own accommodation (not parents' house)?",
    },

    # 32. Medical insurance for family
    {
        "text": "My salary is 14 lakhs. I pay 20,000 for family floater health insurance covering me, wife, and 2 kids.",
        "expected_fields": {
            "salary": 1_400_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": 20_000,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 33. Non-metro city explicit
    {
        "text": "I live in Pune, earn 10 LPA, pay 15,000 rent per month. HRA from employer is 3 lakhs per year.",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": 300_000,
            "rent": 180_000,
            "is_metro": False,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 34. Super high salary
    {
        "text": "I earn 5 crore per annum as a senior executive. No HRA, own house. 80C 1.5L, NPS 50k.",
        "expected_fields": {
            "salary": 50_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 35. All fields present, Hinglish
    {
        "text": "35 saal ki umar, 20 lakh salary, Mumbai mein 30k rent deta hoon, employer se 5 lakh HRA milta hai. 80C 1.5L, NPS 50k, apna 25k medical insurance, parents (senior citizen) ka 50k. Ghar ka loan nahi.",
        "expected_fields": {
            "salary": 2_000_000,
            "hra": 500_000,
            "rent": 360_000,
            "is_metro": True,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 50_000,
            "parents_senior_citizen": True,
            "home_loan_interest": None,
            "age": 35,
        },
        "expected_clarification": None,
    },

    # 36. Incomplete Hinglish
    {
        "text": "Main kuch invest karta hoon aur mera salary thik thak hai.",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Could you tell me your annual gross salary in rupees?",
    },

    # 37. Only 80D mentioned
    {
        "text": "I pay 25k for health insurance for myself. Salary is 8 LPA.",
        "expected_fields": {
            "salary": 800_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": 25_000,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 38. Income in words
    {
        "text": "I draw a salary of twelve lakhs per year from my employer in Kolkata.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": None,
            "rent": None,
            "is_metro": True,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Do you receive HRA from your employer? Do you live in rented accommodation?",
    },

    # 39. With ELSS mention (counts as 80C)
    {
        "text": "Salary 15L. I do SIP of 10,000 per month in ELSS funds (tax saving). Also have LIC premium 25,000 per year.",
        "expected_fields": {
            "salary": 1_500_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 145_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 40. With provident fund mention
    {
        "text": "12 lakh per year salary. EPF contribution around 1 lakh per year. I also pay 15,000 rent per month in Bangalore.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": None,
            "rent": 180_000,
            "is_metro": None,
            "investment_80c": 100_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Do you receive HRA from your employer?",
    },

    # 41. No salary, only deductions and rent
    {
        "text": "80C is done for 1.5 lakhs. Home loan EMI is around 25,000 per month of which 15,000 is interest.",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 180_000,
            "age": None,
        },
        "expected_clarification": "What is your annual gross salary?",
    },

    # 42. Contradictory ages
    {
        "text": "I am 25 years old but I have parents who are 55 years old (senior citizens). Salary 10 LPA.",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": False,
            "home_loan_interest": None,
            "age": 25,
        },
        "expected_clarification": "Your parents are 55 years old, which is below the senior citizen threshold (60 years). They will not qualify for the higher 80D limit. Do you still want to proceed?",
    },

    # 43. Income in salary slip terms
    {
        "text": "Basic: 60,000/month. HRA: 24,000/month. Special allowance: 16,000/month. I pay 20,000 rent in Delhi.",
        "expected_fields": {
            "salary": 1_200_000,
            "hra": 288_000,
            "rent": 240_000,
            "is_metro": True,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 44. Deductions exceed income
    {
        "text": "My salary is 4 lakhs. I invest 1.5 lakhs in 80C, 50,000 in NPS, and my home loan interest is 2 lakhs.",
        "expected_fields": {
            "salary": 400_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": 200_000,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 45. English with typos
    {
        "text": "i earn 10 LPA, i hav 80c of 1 lakh, medicle insurance 20000, i liv in mumbai n pay 20k rent evry month",
        "expected_fields": {
            "salary": 1_000_000,
            "hra": None,
            "rent": 240_000,
            "is_metro": True,
            "investment_80c": 100_000,
            "investment_80ccd1b": None,
            "medical_80d_self": 20_000,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Do you receive HRA from your employer?",
    },

    # 46. Formal document style
    {
        "text": "Name: Rahul Sharma. Age: 32. Annual Gross Salary: Rs. 24,00,000. HRA Received: Rs. 7,20,000. Rent Paid (annual): Rs. 3,60,000. City: Mumbai. 80C Investments: Rs. 1,50,000. 80CCD(1B): Rs. 50,000. 80D Self: Rs. 25,000. 80D Parents (Senior): Rs. 50,000. Home Loan Interest: Rs. 1,80,000.",
        "expected_fields": {
            "salary": 2_400_000,
            "hra": 720_000,
            "rent": 360_000,
            "is_metro": True,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 50_000,
            "parents_senior_citizen": True,
            "home_loan_interest": 180_000,
            "age": 32,
        },
        "expected_clarification": None,
    },

    # 47. Partial Hinglish asking for advice
    {
        "text": "Bhai, 15 lakh kamata hoon. Konsa regime better hai mere liye? Sirf standard deduction lene wala hoon.",
        "expected_fields": {
            "salary": 1_500_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 0,
            "investment_80ccd1b": 0,
            "medical_80d_self": 0,
            "medical_80d_parents": 0,
            "parents_senior_citizen": None,
            "home_loan_interest": 0,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 48. Ambiguous: "around" amounts
    {
        "text": "I earn around 8 to 10 lakhs. I pay about 15 to 20k rent per month.",
        "expected_fields": {
            "salary": None,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": None,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": "Could you give me your exact annual salary figure? Also, what is the exact monthly rent you pay?",
    },

    # 49. Question format input
    {
        "text": "How much tax do I pay if I earn 20 lakhs in Bangalore with 80C investments of 1.5 lakhs?",
        "expected_fields": {
            "salary": 2_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": None,
            "medical_80d_self": None,
            "medical_80d_parents": None,
            "parents_senior_citizen": None,
            "home_loan_interest": None,
            "age": None,
        },
        "expected_clarification": None,
    },

    # 50. Full scenario with home loan and no HRA
    {
        "text": "Age 42. I draw 30 lakhs CTC. I bought a house - no rent but home loan interest is 2.5 lakhs per year (capped at 2L I know). 80C is maxed. NPS 50k. Insurance for self 25k, parents both 68 years old 50k.",
        "expected_fields": {
            "salary": 3_000_000,
            "hra": None,
            "rent": None,
            "is_metro": None,
            "investment_80c": 150_000,
            "investment_80ccd1b": 50_000,
            "medical_80d_self": 25_000,
            "medical_80d_parents": 50_000,
            "parents_senior_citizen": True,
            "home_loan_interest": 250_000,
            "age": 42,
        },
        "expected_clarification": None,
    },
]

if __name__ == "__main__":
    print(f"Total plain language test cases: {len(PLAIN_LANGUAGE_INPUTS)}")
    for i, case in enumerate(PLAIN_LANGUAGE_INPUTS, 1):
        print(f"\n{i}. {case['text'][:80]}...")
        print(f"   Clarification: {case['expected_clarification']}")
