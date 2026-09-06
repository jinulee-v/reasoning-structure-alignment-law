/* ---------------------------
   Statutory rules (excerpt)
   --------------------------- */

/* passenger information */
class(main_plus).
flight_region(us_to_south_america).       /* Charlotte (U.S.)  -> Bogotá (Colombia) */
flight_ticket_cost(284).

/* Main-Plus includes 2 free checked bags (Main-Cabin allowance of 1 + 1 extra) */
free_checked_bags(2).

/* ----------  Base checked-bag fees for this region (Main Cabin / Main Plus) -------- */
base_bag_fee(BagIndex, 0)  :- BagIndex =< 2.              /* 1st & 2nd bag - free   */
base_bag_fee(BagIndex, 200):- BagIndex  > 2, BagIndex =< 4. /* 3rd & 4th bag - $200  */
base_bag_fee(BagIndex, 200):- BagIndex  > 4.               /* 5th + bag - $200      */

/* ----------  Oversize fees (dimension = L+W+H) ------------- */
oversize_fee(Dim, us_to_south_america, 0  ) :- Dim =< 62.
oversize_fee(Dim, us_to_south_america, 30 ) :- Dim > 62, Dim =< 65.
oversize_fee(Dim, us_to_south_america, 150) :- Dim > 65, Dim =< 115.

/* ----------  Over-weight fees ------------------------------ */
overweight_fee(W, _, 0)  :- W =< 50.
overweight_fee(W, _, 30) :- W > 50,  W =< 53.
overweight_fee(W, Region, 100):- W > 53, W =< 70, Region \= cuba.
overweight_fee(W, us_to_south_america, 200):- W > 70, W =< 100.

/* The applicable special-charge on a bag is the HIGHER of overweight or oversize */
special_charge(Dim, W, Region, Charge):-
    oversize_fee(Dim, Region, OFee),
    overweight_fee(W, Region, WFee),
    max_list([OFee,WFee], Charge).

/* ---------------------------
   Case facts - Joseph's bags
   --------------------------- */

/* bag(Index, Length, Width, Height, Weight) */
bag(1, 19, 11,  8,  7).    /* small backpack - carry-on */
bag(2, 39, 12, 15, 85).    /* checked */
bag(3, 54, 33, 27, 65).    /* checked */
bag(4, 41, 31, 17,100).    /* checked */
bag(5, 42, 29, 18, 94).    /* checked */

/* Carry-on test (must not exceed 22*14*9) */
carry_on(Index) :-
    bag(Index,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* Checked bags are all Joseph's bags that are NOT carry-ons                    */
/* They retain the order 1...n after removal of carry-ons for fee computation.    */
checked_bag(NewIdx, BagId) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), List),
    nth1(NewIdx, List, BagId).

/* --------------  Cost of each checked bag ------------------ */
checked_bag_cost(NewIdx, Cost):-
    checked_bag(NewIdx, BagId),
    bag(BagId,L,W,H,Wt),
    Dim is L+W+H,
    flight_region(Region),
    special_charge(Dim, Wt, Region, SpecialFee),
    base_bag_fee(NewIdx, BaseFee),
    Cost is BaseFee + SpecialFee.

/* --------------  Total cost -------------------------------- */
total_bag_cost(Total):-
    findall(C, checked_bag_cost(_,C), Costs),
    sum_list(Costs, Total).

total_cost(Total):-
    total_bag_cost(Bags),
    flight_ticket_cost(Ticket),
    Total is Ticket + Bags.

/* ------------------  Query & output ------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.