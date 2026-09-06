% ---------- Facts describing the itinerary ----------
route(europe_us).                        % Zurich (Europe) -> Sacramento (U.S.)
passenger_class(main_cabin).
ticket_cost(612).

% bag(ID, Length, Width, Height, Weight).
bag(1,18,13, 6,11).
bag(2,54,33,28,51).
bag(3,35,16,12,63).
bag(4,34,24,10,58).
bag(5,35,21, 9,66).
bag(6,37,17, 9,61).
bag(7,39,26,16,51).
bag(8,36,16,13,52).

% ---------- Rules for free carry-on / personal item ----------
is_personal(B) :-
    bag(B,L,W,H,_),
    L =< 18, W =< 14, H =< 8.

is_carry_on(B) :-
    bag(B,L,W,H,_),
    L =< 22, W =< 14, H =< 9,
    \+ is_personal(B).                 % don't double-count the personal item

% ---------- Checked-bag identification ----------
checked_bag(B) :-
    bag(B,_,_,_,_),
    \+ is_personal(B),
    \+ is_carry_on(B).

checked_bags(List) :-
    findall(B,checked_bag(B),L0),
    msort(L0,List).

bag_ordinal(Bag,Ord) :-
    checked_bags(List),
    nth1(Ord,List,Bag).

% ---------- Base fee for 1st, 2nd, 3rd... checked bags (Main Cabin, Europe<->US) ----------
base_fee(1,0).                 % 1st bag free (trans-atlantic benefit)
base_fee(2,100).
base_fee(Ord,200) :- Ord>=3.

bag_base_fee(Bag,Fee) :-
    bag_ordinal(Bag,Ord),
    base_fee(Ord,Fee).

% ---------- Oversize / overweight surcharges (Europe<->US) ----------
size(B,S) :-
    bag(B,L,W,H,_),
    S is L+W+H.

oversize_fee(B,0) :-
    size(B,S), S =< 62.
oversize_fee(B,30) :-
    size(B,S), S > 62, S =< 65.
oversize_fee(B,150) :-
    size(B,S), S > 65, S =< 115.

overweight_fee(B,0) :-
    bag(B,_,_,_,W), W =< 50.
overweight_fee(B,30) :-
    bag(B,_,_,_,W), W > 50, W =< 53.
overweight_fee(B,100) :-
    bag(B,_,_,_,W), W > 53, W =< 70.

surcharge(B,Fee) :-
    oversize_fee(B,O),
    overweight_fee(B,W),
    (O >= W -> Fee = O ; Fee = W).

% ---------- Total luggage cost ----------
bag_cost(B,Total) :-
    bag_base_fee(B,Base),
    surcharge(B,Surch),
    Total is Base + Surch.

total_bag_cost(Sum) :-
    findall(C,(checked_bag(B),bag_cost(B,C)),Costs),
    sum_list(Costs,Sum).

% ---------- Grand total ----------
total_cost(Total) :-
    ticket_cost(T),
    total_bag_cost(Bags),
    Total is T + Bags.

% ---------- Query ----------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.