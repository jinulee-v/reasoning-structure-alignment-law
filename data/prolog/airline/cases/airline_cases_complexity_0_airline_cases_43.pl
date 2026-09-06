/* ----------  Statutory rules needed for this case  ---------- */

/* the itinerary we deal with is China  <->  U.S.  */
region(to_from_china).

/* complimentary allowance : Premium-Economy = first 2 checked bags free */
free_checked_bags(premium_economy, 2).

/* base fee for the 1st, 2nd, 3rd, 4th+ checked bag on routes
   "To / From ... China ..." when travelling in Premium-Economy        */
base_fee(premium_economy, to_from_china, BagNumber, 0) :-
    BagNumber =< 2.                         /* 1st & 2nd bags free */

base_fee(premium_economy, to_from_china, BagNumber, 200) :-
    BagNumber >= 3.                         /* 3rd, 4th ... = $200   */


/* ---------  Oversize fees (inches = L+W+H)  --------- */
oversize_fee(to_from_china, SizeInches, 0)  :- SizeInches =< 62.
oversize_fee(to_from_china, SizeInches, 30) :- 
        SizeInches > 62, SizeInches =< 65.
oversize_fee(to_from_china, SizeInches, 200) :- 
        SizeInches > 65, SizeInches =< 115.

/* ---------  Over-weight fees (pounds)  --------- */
overweight_fee(to_from_china, W, 0)   :- W =< 50.
overweight_fee(to_from_china, W, 30)  :- W  > 50, W =< 53.
overweight_fee(to_from_china, W, 100) :- W  > 53, W =< 70.
overweight_fee(to_from_china, W, 450) :- W  > 70, W =< 100.

/* the surcharge for a bag that is both oversize and overweight is
   the higher of the two                                                     */
surcharge(Region, Size, Weight, Fee) :-
        oversize_fee(Region, Size, O),
        overweight_fee(Region, Weight, W),
        (O >= W -> Fee = O ; Fee = W).


/* ----------  Facts for Linda's trip  ---------- */

traveller(linda).
class(linda, premium_economy).
ticket_price(linda, 1141).
itinerary(linda, to_from_china).

/* Checked bags (carry-on / personal items cost $0 and are omitted)  */
/* bag(No, L, W, H, WeightLbs) */
bag(1, 35,20,10, 60).   /* luggage #1 */
bag(2, 49,31,23, 51).   /* luggage #2 */
bag(3, 34,16,14, 92).   /* backpack   */
bag(4, 49,26,22, 83).   /* luggage #3 */

/* ----------  Derived calculations  ---------- */

/* helper: linear dimension sum */
size_sum(L,W,H,S) :- S is L+W+H.

/* fee for an individual checked bag */
bag_fee(BagNo, Fee) :-
        bag(BagNo, L,W,H, Weight),
        traveller(linda),
        itinerary(linda, Region),
        class(linda, Class),
        size_sum(L,W,H,Size),
        surcharge(Region, Size, Weight, Surcharge),
        base_fee(Class, Region, BagNo, Base),
        Fee is Base + Surcharge.

/* total for all checked bags */
total_bag_fees(Total) :-
        findall(F, bag_fee(_,F), List),
        sum_list(List, Total).

/* complete trip cost = ticket + bags  (+ $0 special-needs) */
total_cost(Total) :-
        ticket_price(linda, Ticket),
        total_bag_fees(Bags),
        Total is Ticket + Bags.

/* ----------  Produce the answer  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.