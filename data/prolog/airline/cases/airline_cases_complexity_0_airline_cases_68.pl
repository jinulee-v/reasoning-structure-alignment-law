/* ----------  RULES FROM THE STATUTE (only what is needed for this case) ---------- */

/* Route of the flight */
route(within_us_canada).        /* Vancouver (Canada)  ->  Portland (U.S.) */

/* ---------------- 1. BASE CHECKED-BAG FEE (Basic-Economy, within U.S./Canada)----- */
base_checked_bag_fee(1, within_us_canada, 35).      /* 1st checked bag   */
base_checked_bag_fee(2, within_us_canada, 45).      /* 2nd checked bag   */
base_checked_bag_fee(3, within_us_canada, 150).     /* 3rd checked bag   */
base_checked_bag_fee(N, within_us_canada, 200) :-   /* 4th bag and up    */
    N >= 4.

/* ---------------- 2. OVERSIZE SURCHARGE (within U.S./Canada) --------------------- */
oversize_surcharge(Size, within_us_canada, 30)  :-  % 62  < size =< 65 in
    Size > 62, Size =< 65.
oversize_surcharge(Size, within_us_canada, 200) :-  % 65  < size =< 115 in
    Size > 65, Size =< 115.
oversize_surcharge(Size, _, 0) :-                   % =< 62 in  ->  no surcharge
    Size =< 62.

/* ---------------- 3. OVERWEIGHT SURCHARGE (within U.S./Canada) ------------------- */
overweight_surcharge(W, within_us_canada, 0)  :- W =< 50.         % normal weight
overweight_surcharge(W, within_us_canada, 30) :- W  > 50, W =< 53.
overweight_surcharge(W, within_us_canada, 100):- W  > 53, W =< 70.
overweight_surcharge(W, within_us_canada, 200):- W  > 70, W =< 100.

/* When a bag is both oversize and overweight you pay the HIGHER (max) surcharge. */
bag_surcharge(Size, Weight, Route, Surcharge) :-
    oversize_surcharge(Size, Route, OS),
    overweight_surcharge(Weight, Route, OW),
    Surcharge is max(OS, OW).

/* ---------------- 4. DIMENSION SUM (length+width+height) ------------------------ */
dimension_sum(L, W, H, Sum) :- Sum is L + W + H.

/* ----------  FACTS ABOUT THE PASSENGER, ITEMS & TICKET -------------------------- */

/* ticket price */
ticket_price(385).

/* items:  item(ID, L, W, H, Weight).   (all measures in inches / pounds) */
item(1, 18, 12,  6,  8).     /* backpack - personal item                */
item(2, 49, 31, 24, 63).     /* luggage box                             */
item(3, 33, 21,  9, 61).     /* luggage box                             */
item(4, 41, 25, 14, 57).     /* big backpack                            */
item(5, 38, 14, 11, 99).     /* luggage box                             */

/* Identify the 1 personal item that flies free (dimensions =< 18*14*8). */
personal_item(ID) :-
    item(ID,L,W,H,_),
    L =< 18, W =< 14, H =< 8,
    ID = 1.              /* in this case we know item 1 is the only one */

/* A checked bag is any item that is NOT the chosen personal item */
checked_bag(ID) :-
    item(ID,_,_,_,_),
    \+ personal_item(ID).

/* Enumerate checked bags in the order they will be charged */
checked_bag_with_position(ID, Pos) :-
    findall(I, checked_bag(I), List),
    nth1(Pos, List, ID).

/* -------------- 5. FEE FOR EACH CHECKED BAG ------------------------------------- */
checked_bag_fee(ID, Fee) :-
    checked_bag_with_position(ID, Pos),
    route(Route),
    base_checked_bag_fee(Pos, Route, Base),
    item(ID,L,W,H,Weight),
    dimension_sum(L,W,H,Size),
    bag_surcharge(Size, Weight, Route, Surcharge),
    Fee is Base + Surcharge.

/* -------------- 6. TOTALS ------------------------------------------------------- */
bags_total_fee(Total) :-
    findall(F, checked_bag_fee(_,F), Fees),
    sum_list(Fees, Total).

total_cost(Total) :-
    ticket_price(Tix),
    bags_total_fee(Bags),
    Total is Tix + Bags.

/* ---------------- QUERY --------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.