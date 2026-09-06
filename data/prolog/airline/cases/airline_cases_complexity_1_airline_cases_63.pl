/* --------------------  Statutory rules  -------------------- */

/* cabin and region for this itinerary */
cabin(business).
region(us_domestic).

/* flight ticket price */
flight_ticket(170).

/* --------------------  Passenger's items  -------------------- */
/* bag(ID, Length, Width, Height, Weight). */
bag(1, 19, 12,  9,  9).
bag(2, 38, 12, 14, 52).
bag(3, 43, 28, 23, 52).
bag(4, 45, 25, 17, 96).
bag(5, 43, 16, 19, 51).
bag(6, 34, 18, 13, 83).
bag(7, 44, 27, 19, 72).
bag(8, 45, 26, 24, 86).

/* --------------------  Carry-on test  -------------------- */
carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.     /* fits the 22*14*9 limit */

/* --------------------  Base checked-bag fees (Business, US)  -------------------- */
base_fee(1,0).           /* 1st checked bag */
base_fee(2,0).           /* 2nd checked bag */
base_fee(3,150).         /* 3rd checked bag */
base_fee(Pos,200) :-     /* 4th bag and beyond */
    Pos >= 4.

/* --------------------  Oversize fees (inches = L+W+H)  -------------------- */
oversize_fee(L,W,H,Fee) :-
    S is L+W+H,
    (   S =< 62  -> Fee = 0
    ;   S =< 65  -> Fee = 30
    ;   S =< 115 -> Fee = 200
    ;   Fee = 99999        /* not accepted - not reached in this case */
    ).

/* --------------------  Overweight fees (pounds)  -------------------- */
overweight_fee(W,Fee) :-
    (   W =< 50  -> Fee = 0
    ;   W =< 53  -> Fee = 30
    ;   W =< 70  -> Fee = 100
    ;   W =< 100 -> Fee = 200
    ;   Fee = 99999        /* not accepted - not reached in this case */
    ).

/* --------------------  Checked-bag list (order preserved)  -------------------- */
checked_bag_ids(List) :-
    findall(ID, (bag(ID,_,_,_,_), \+ carry_on(ID)), List).

/* --------------------  Fee for one checked bag  -------------------- */
bag_total_fee(Index, BagID, TotalFee) :-
    bag(BagID,L,W,H,Weight),
    oversize_fee(L,W,H,OSFee),
    overweight_fee(Weight,OWFee),
    ExtraFee is max(OSFee,OWFee),          /* only the higher of the two applies */
    base_fee(Index,Base),
    TotalFee is Base + ExtraFee.

/* --------------------  All luggage fees  -------------------- */
bag_fees(Total) :-
    checked_bag_ids(IDs),
    findall(Fee,
            (nth1(Index, IDs, BagID),
             bag_total_fee(Index, BagID, Fee)),
            Fees),
    sum_list(Fees, Total).

/* --------------------  Grand total  -------------------- */
total_cost(GrandTotal) :-
    bag_fees(Bags),
    flight_ticket(Ticket),
    GrandTotal is Bags + Ticket.

/* --------------------  Query & output  -------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.