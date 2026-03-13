"""
Simple Cycling Event Planning Tool
----------------------------------
This is a beginner-friendly, single-file program that helps estimate:

1) SAG vehicles needed
2) Portable bathrooms needed
3) Staff/volunteers needed
4) Full event summary

This is a temporary version until we build the full multi-module system.
It uses simple rules-of-thumb that match real cycling event planning.
"""

# ------------------------------------------------------------
# 1. BASIC CALCULATION FUNCTIONS
# ------------------------------------------------------------

import math


def calculate_circle_area(radius):
    """
    Calculate the area of a circle using the formula:
        area = π * r²

    Radius is expected to be a non-negative number. Returns the
    computed area as a float.
    """
    if radius < 0:
        raise ValueError("Radius cannot be negative")
    return math.pi * radius * radius

def calculate_sag_vehicles(total_riders):
    """
    SAG Rule-of-thumb:
        1 SAG per 150 riders (rounded up)
    """
    sag_needed = (total_riders + 149) // 150
    return sag_needed


def calculate_bathrooms(total_riders):
    """
    Portable Bathroom Rule-of-thumb:
        1 bathroom per 50 riders
    
    (We can refine this later based on event duration.)
    """
    bathrooms_needed = (total_riders + 49) // 50
    return bathrooms_needed


def calculate_staff_and_volunteers(total_riders, num_routes):
    """
    Simple staffing assumptions:
        - Registration: 1 volunteer per 25 riders
        - Rest Stop Volunteers: 6 per rest stop
        - Mechanic Rule-of-thumb: 1 per 250 riders
        - Signage Crew: 2 people per route
    """
    registration_vols = (total_riders + 24) // 25
    rest_stop_vols = num_routes * 6
    mechanics = (total_riders + 249) // 250
    signage = num_routes * 2

    return {
        "registration_volunteers": registration_vols,
        "rest_stop_volunteers": rest_stop_vols,
        "mechanics": mechanics,
        "signage_team_members": signage
    }


# ------------------------------------------------------------
# 2. MENU OPTION HANDLERS
# ------------------------------------------------------------

def option_sag():
    total = int(input("\nHow many total riders? "))
    sag = calculate_sag_vehicles(total)
    print(f"\nYou need **{sag} SAG vehicles**.\n")


def option_bathrooms():
    total = int(input("\nHow many total riders? "))
    bathrooms = calculate_bathrooms(total)
    print(f"\nYou need approximately **{bathrooms} portable bathrooms**.\n")


def option_staff():
    total = int(input("\nHow many total riders? "))
    num_routes = int(input("How many routes/distances? "))

    results = calculate_staff_and_volunteers(total, num_routes)

    print("\nStaff & Volunteer Estimates:")
    print(f"  Registration Volunteers: {results['registration_volunteers']}")
    print(f"  Rest Stop Volunteers:    {results['rest_stop_volunteers']}")
    print(f"  Mechanics Needed:        {results['mechanics']}")
    print(f"  Signage Team Members:    {results['signage_team_members']}\n")


def option_full_event():
    """
    Combines all calculations and prints a complete summary.
    """
    print("\n--- Full Event Input ---")
    total = int(input("Total riders across all routes: "))
    num_routes = int(input("Number of route distances offered: "))

    sag = calculate_sag_vehicles(total)
    bathrooms = calculate_bathrooms(total)
    staff = calculate_staff_and_volunteers(total, num_routes)

    print("\n====== EVENT SUMMARY ======")
    print(f"Total Riders: {total}")
    print(f"Number of Routes: {num_routes}\n")

    print(f"SAG Vehicles Needed: {sag}")
    print(f"Portable Bathrooms:  {bathrooms}\n")

    print("Staff & Volunteer Estimates:")
    print(f"  Registration Volunteers: {staff['registration_volunteers']}")
    print(f"  Rest Stop Volunteers:    {staff['rest_stop_volunteers']}")
    print(f"  Mechanics Needed:        {staff['mechanics']}")
    print(f"  Signage Team Members:    {staff['signage_team_members']}")
    print("============================\n")


# ------------------------------------------------------------
# 3. MENU LOOP
# ------------------------------------------------------------

def main_menu():
    while True:
        print("\n=== CYCLING EVENT PLANNING MENU ===")
        print("1) Calculate SAG vehicles")
        print("2) Calculate portable bathrooms")
        print("3) Estimate staff & volunteers")
        print("4) Full event summary")
        print("5) Exit")

        choice = input("Select an option: ")

        if choice == "1":
            option_sag()
        elif choice == "2":
            option_bathrooms()
        elif choice == "3":
            option_staff()
        elif choice == "4":
            option_full_event()
        elif choice == "5":
            print("\nGoodbye!\n")
            break
        else:
            print("\nInvalid choice. Please try again.\n")


# ------------------------------------------------------------
# 4. PROGRAM ENTRY POINT
# ------------------------------------------------------------

if __name__ == "__main__":
    main_menu()