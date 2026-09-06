/* ---------- Rules derived from the statutes ---------- */

% carry-on size limit
carry_on_limit(22,14,9).

% a bag is a carry-on if it does not exceed the carry-on limits
carry_on(Bag) :-
    bag(Bag,L,W,H,_),
    carry_on_limit(LC,WC,HC),
    L =< LC, W =< WC, H =< HC.

% size (length+width+height) of a bag
bag_size(Bag,S) :-
    bag(Bag,L,W,H,_),
    S is L+W+H.

% oversize fee (Charlotte <-> Haiti counts as U.S. <-> Caribbean)
oversize_fee(Bag,Fee) :-
    bag_size(Bag,S),
    (  S =< 62 -> Fee = 0
    ;  S =< 65 -> Fee = 30           % 62-65 in
    ;  S =< 115 -> Fee = 200         % 65-115 in
    ).

% overweight fee
overweight_fee(Bag,Fee) :-
    bag(Bag,_,_,_,W),
    (  W =< 50  -> Fee = 0
    ;  W =< 53  -> Fee = 30
    ;  W =< 70  -> Fee = 100
    ;  W =< 100 -> Fee = 200
    ).

% for a bag that is both oversize and overweight, charge ONLY the higher
extra_fee(Bag,Fee) :-
    oversize_fee(Bag,OverSize),
    overweight_fee(Bag,OverWeight),
    (OverSize >= OverWeight -> Fee = OverSize ; Fee = OverWeight).

/* ---------- Facts for this case ---------- */

% bag(Name,Length,Width,Height,Weight)
bag(bag1,21,12, 9,11).
bag(bag2,35,20, 9,86).
bag(bag3,38,15,12,51).
bag(bag4,34,18,13,65).
bag(bag5,34,17,12,78).
bag(bag6,35,16,12,93).
bag(bag7,35,15,13,51).
bag(bag8,36,17,11,84).

% ticket price
ticket_price(59).

/* ---------- Checked-bag numbering ---------- */

% list of bags that are NOT carry-ons -> become checked bags
checked_bag_list(Checked) :-
    findall(B, (bag(B,_,_,_,_), \+ carry_on(B)), Checked).

% index of each checked bag (1-based)
checked_index(Bag,Idx) :-
    checked_bag_list(L), nth1(Idx,L,Bag).

/* ---------- Base checked-bag fee for Premium Economy (CLT <-> Haiti) ---------- */

% Premium Economy gets 1st & 2nd checked bags free; every bag from #3 on costs $200
base_checked_fee(Bag,Fee) :-
    checked_index(Bag,Idx),
    (Idx =< 2 -> Fee = 0 ; Fee = 200).

/* ---------- Total fee for each checked bag ---------- */

bag_total_fee(Bag,Total) :-
    base_checked_fee(Bag,Base),
    extra_fee(Bag,Extra),
    Total is Base + Extra.

/* ---------- Sum of all checked-bag fees ---------- */

checked_bags_total(Cost) :-
    findall(F, (checked_index(Bag,_), bag_total_fee(Bag,F)), L),
    sum_list(L,Cost).

/* ---------- Grand total (ticket + bags) ---------- */

total_cost(Total) :-
    ticket_price(T),
    checked_bags_total(Bags),
    Total is T + Bags.

/* ---------- Query & output ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.