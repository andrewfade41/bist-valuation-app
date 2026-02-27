from dcf_model import calculate_dcf
iv, cp, details, err = calculate_dcf("TUPRS", 0.25, 0.15, 0.35)
print(iv, err)
print(details)
