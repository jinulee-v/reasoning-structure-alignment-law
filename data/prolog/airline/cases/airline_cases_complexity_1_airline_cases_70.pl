/* ----------  RULES (statutes distilled for this itinerary) ---------- */

/* this itinerary: Washington-D.C. (US) <-> Paris (Europe) */
route(europe_us).

/* passenger booking */
passenger_class(main_plus).                /* Main Plus (Main Cabin with 1 extra free bag) */

/* free checked-bag allowance -----------------------------------------
   - Trans-Atlantic (US-Europe) Main-Cabin customers get the 1st bag free
   - Main Plus adds 1 extra free bag (max 2)
-----------------------------------------------------------------------*/
free_checked_bags(2).

/* checked-bag fee table for this route (after free allowance) */
checked_bag_fee(BagIndex, 0)  :- free_checked_bags(F), BagIndex =< F.
checked_bag_fee(BagIndex, 200):- free_checked_bags(F), BagIndex > F.

/* oversize fees: Europe <-> US ---------------------------------------*/
oversize_fee(DimSum, 0)    :- DimSum =< 62.
oversize_fee(DimSum, 30)   :- DimSum > 62, DimSum =< 65.
oversize_fee(DimSum, 150)  :- DimSum > 65, DimSum =< 115.

/* overweight fees: Europe <-> US -------------------------------------*/
overweight_fee(Weight, 0)   :- Weight =< 50.
overweight_fee(Weight, 30)  :- Weight  > 50, Weight =< 53.
overweight_fee(Weight, 100) :- Weight  > 53, Weight =< 70.

/* special-handling fee for a bag is the higher of the 2 */
special_fee(DimSum, Weight, Fee) :-
    oversize_fee(DimSum, OS),
    overweight_fee(Weight, OW),
    (OS >= OW -> Fee = OS ; Fee = OW).

/* -----------------------  THE CASE FACTS  ---------------------------*/

/* flight ticket price */
flight_ticket(494).

/* the 7 checked bags (index, dimension-sum inches, weight lbs) */
bag(1, 65, 53).   /* luggage box 33*22*10        */
bag(2, 63, 57).   /* backpack   34*15*14        */
bag(3, 65, 70).   /* luggage box 38*18*9         */
bag(4, 91, 62).   /* luggage box 42*31*18        */
bag(5, 63, 52).   /* luggage box 33*16*14        */
bag(6, 84, 57).   /* luggage box 42*23*19        */
bag(7, 63, 62).   /* backpack   33*16*14        */

/* total fee for one bag = checked-bag fee + special fee */
bag_total_fee(Index, Total) :-
    bag(Index, Dim, Wt),
    checked_bag_fee(Index, CBFee),
    special_fee(Dim, Wt, SpFee),
    Total is CBFee + SpFee.

/* sum a list */
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,R), S is R+H.

/* -------------------  COMPUTING THE FINAL COST  ---------------------*/
total_bag_fees(Total) :-
    findall(Fee,
            (bag(Index,_,_), bag_total_fee(Index, Fee)),
            Fees),
    sum_list(Fees, Total).

total_cost(Total) :-
    flight_ticket(Tk),
    total_bag_fees(BagTotal),
    Total is Tk + BagTotal.

/* ---------------------------  QUERY  --------------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.