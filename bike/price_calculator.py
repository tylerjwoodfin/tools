"""
A super basic tool to show myself the price per ride on my bike.
After each ride, I call this script to see how over time, the cost per ride decreases.
"""

from cabinet import Cabinet

def main():
    """
    calculate the bike price per ride
    """
    cabinet = Cabinet()
    bike_price = cabinet.get('bike', 'price', return_type=int) or 0
    rides = cabinet.get('bike', 'rides', return_type=int) or 0
    rides += 1

    # increment rides
    cabinet.put('bike', 'rides', rides)

    print(f"Thank you for riding!\nYou've taken {rides} rides.")
    print(f"Your bike price per ride is now: ${bike_price / rides:.2f}.")

if __name__ == '__main__':
    main()
