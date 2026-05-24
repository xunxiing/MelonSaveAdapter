i = INPUT("I", "Number")
a = INPUT("A", "Number")

if __name__ == "__main__":
    if i == 1:
        a = a + 3
        result_text = ToString(a)
    else:
        a = a + 5
        result_text = ToString(a)

    affected_number = a + 10

    OUTPUT(a, "Branched Number")
    OUTPUT(result_text, "Branched Text")
    OUTPUT(affected_number, "Affected Number")
