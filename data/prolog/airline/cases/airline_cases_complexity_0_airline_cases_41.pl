/* ==========  Basic facts about the itinerary  ========== */
class(premium_economy).

% the itinerary is China  <->  U.S.
region(china_usa).

ticket_price(1035).

/* ==========  Bags:  length, width, height, weight  ========== */
bag(bag1,18,12, 8,  6).      /* personal item                        */
bag(bag2,41,26,22, 53).      /* checked                              */
bag(bag3,36,15,14, 97).      /* checked                              */
bag(bag4,44,27,22, 52).      /* checked                              */
bag(bag5,42,30,19, 88).      /* checked                              */

/* ----------------------------------------------------------- */
/* ------------  helpers to classify the bag  ---------------- */
/* ----------------------------------------------------------- */

dim_sum(Bag,S) :- bag(Bag,L,W,H,_),  S is L+W+H.
weight(Bag,W)  :- bag(Bag,_,_,_,W).

/* personal item =< 18*14*8 inches                               */
personal_item(Bag) :-
    bag(Bag,L,W,H,_),
    L =< 18, W =< 14, H =< 8.

/* all other bags that are not personal items are checked        */
checked_bag(Bag) :-
    bag(Bag,_,_,_,_),
    \+ personal_item(Bag).

/* ----------------------------------------------------------- */
/* --------  Base fee for 1st / 2nd / 3rd / 4th bag  ---------- */
/* ----------------------------------------------------------- */

% list of checked bags in the order they appear in the facts
checked_bag_list(List) :-
    findall(B, checked_bag(B), List).

/* For this itinerary (China<->USA - Premium Economy)
      1st bag : $0
      2nd bag : $0
      3rd bag : $200
      4th+    : $200 each                                       */

base_checked_fee(Index,Fee) :-
      Index =< 2,         Fee = 0 ;
      Index >= 3,         Fee = 200.

/* ----------------------------------------------------------- */
/* -------------  Oversize / Over-weight fees  ---------------- */
/* ----------------------------------------------------------- */

/* ---- oversize (China <-> USA) ----
      >62 - 65 in   : $30
      >65 - 115 in  : $200                                      */
oversize_fee(Bag,Fee) :-
    dim_sum(Bag,S),
    (S > 65  ->  Fee = 200
    ;S > 62  ->  Fee = 30
    ;           Fee = 0).

/* ---- overweight (China <-> USA) ----
      >50 - 53 lb   : $30
      >53 - 70 lb   : $100
      >70 -100 lb   : $450                                      */
overweight_fee(Bag,Fee) :-
    weight(Bag,W),
    (W > 70   ->  Fee = 450
    ;W > 53   ->  Fee = 100
    ;W > 50   ->  Fee = 30
    ;            Fee = 0).

/*  When both oversize and overweight apply, only the HIGHER of
    the two is charged.                                         */
extra_fee(Bag,Fee) :-
    oversize_fee(Bag,O),
    overweight_fee(Bag,W),
    (O >= W -> Fee = O ; Fee = W).

/* ----------------------------------------------------------- */
/* ----------------  Total checked-bag charges  --------------- */
/* ----------------------------------------------------------- */

bag_charge(Bag,Index,Total) :-
    base_checked_fee(Index,Base),
    extra_fee(Bag,Extra),
    Total is Base + Extra.

total_checked_fee(Total) :-
    checked_bag_list(List),
    findall(Cost,
            (nth1(I,List,Bag), bag_charge(Bag,I,Cost)),
            Costs),
    sumlist(Costs,Total).

/* ----------------------------------------------------------- */
/* ---------------------  Grand total  ----------------------- */
/* ----------------------------------------------------------- */

total_cost(Total) :-
    ticket_price(Ticket),
    total_checked_fee(Checked),
    Total is Ticket + Checked.

/* ----------------------------------------------------------- */
/* ----------------------  Query block  ---------------------- */
/* ----------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.