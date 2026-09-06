/* ---------- Statutory rules (subset needed for this case) ---------- */

% base checked-bag fee for Business Class travel wholly within the U.S.
% Bag #1 and #2 : $0
% Bag #3        : $150
% Bag #4 +      : $200
base_fee(1,0).
base_fee(2,0).
base_fee(3,150).
base_fee(N,200):- N>=4.

% weight allowance (Business Class - complimentary vs. charged bags)
allowed_weight(1,70).
allowed_weight(2,70).
allowed_weight(N,50):- N>=3.

% overweight fee (domestic - U.S. / Canada / PR / USVI)
overweight_fee(Allowed, W,Fee):- W=<Allowed, Fee=0, !.
overweight_fee(_,W,200):- W>70, !.      % 70-100 lbs
overweight_fee(_,W,100):- W>53, !.      % >53-70 lbs
overweight_fee(_,W,30 ):- W>50.         % >50-53 lbs

% oversize fee (domestic - U.S. / Canada / PR / USVI)
oversize_fee(Sum,0)   :- Sum =<62, !.
oversize_fee(Sum,30)  :- Sum =<65, !.   % 62-65 in
oversize_fee(_,200).                     % 65-115 in

% extra fee is the higher of over-weight vs. over-size
extra_fee(OW,OS,OW) :- OW>=OS, !.
extra_fee(_,OS,OS).

/* ---------- Facts for Daniel's flight ---------- */

ticket_cost(69).

% bag(ID, Type, Length, Width, Height, Weight).
bag(1,backpack,20,14,7,  8).
bag(2,backpack,38,14,12,57).
bag(3,backpack,37,13,14,65).
bag(4,backpack,34,17,13,64).
bag(5,backpack,48,28,26,79).
bag(6,backpack,37,14,12,89).
bag(7,backpack,46,20,22,64).
bag(8,backpack,34,16,14,66).
bag(9,luggage_box,46,27,22,51).
bag(10,backpack,48,28,24,58).
bag(11,backpack,39,18,13,51).

% carry-on limits (22*14*9 inches)
carryon_ok(L,W,H):- L=<22, W=<14, H=<9.

is_carryon(ID):- bag(ID,_,L,W,H,_), carryon_ok(L,W,H).

/* ---------- Checked-bag numbering ---------- */

checked_bag_number(ID,Num):-
    findall(B, (bag(B,_,_,_,_,_), \+ is_carryon(B)), List),
    nth1(Num,List,ID).

/* ---------- Cost of an individual checked bag ---------- */

bag_cost(ID,Cost):-
    checked_bag_number(ID,Num),
    bag(ID,_,L,W,H,Wt),
    Sum is L+W+H,
    base_fee(Num,Base),
    allowed_weight(Num,Allow),
    overweight_fee(Allow,Wt,OWF),
    oversize_fee(Sum,OSF),
    extra_fee(OWF,OSF,Extra),
    Cost is Base+Extra.

/* ---------- Total cost ---------- */

total_cost(Total):-
    findall(C, bag_cost(_,C), BagCosts),
    sum_list(BagCosts,BagsTotal),
    ticket_cost(T),
    Total is BagsTotal + T.

/* ---------- Query ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.