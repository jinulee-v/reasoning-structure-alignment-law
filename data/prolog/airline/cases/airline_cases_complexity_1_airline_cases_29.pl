% ---------- STATUTORY RULES (relevant subset) ----------
% Base checked-bag fee for Business Class on flights within the U.S.
% Bag #1 and #2: free | Bag #3: $150 | Bag #4+: $200
bag_base_fee(Num,Fee) :-
    ( Num =< 2 -> Fee = 0
    ; Num =:= 3 -> Fee = 150
    ; Num >= 4  -> Fee = 200).

% Oversize surcharge (length+width+height)
oversize_surcharge(DimSum,S) :-
    ( DimSum > 65 -> S = 200          % >65 -115 in
    ; DimSum > 62 -> S = 30           % >62 -65 in
    ;                    S = 0).

% Overweight surcharge (within U.S. region)
overweight_surcharge(Weight,S) :-
    ( Weight > 70  -> S = 200         % 70-100 lbs
    ; Weight > 53  -> S = 100         % >53-70 lbs
    ; Weight > 50  -> S = 30          % >50-53 lbs
    ;                     S = 0).

% Total surcharge on a bag is the higher of oversize / overweight
surcharge(BagId,Sur) :-
    bag(BagId,L,W,H,Weight),
    DimSum is L+W+H,
    oversize_surcharge(DimSum,S1),
    overweight_surcharge(Weight,S2),
    (S1 >= S2 -> Sur = S1 ; Sur = S2).

% Bag fee = base fee (by sequence) + surcharge
bag_fee(BagId,SeqNum,Fee) :-
    bag_base_fee(SeqNum,Base),
    surcharge(BagId,Sur),
    Fee is Base + Sur.

% ---------- CASE FACTS ----------
ticket_price(286).

% Bag facts: bag(Id,Length,Width,Height,Weight).
% (Carry-on item #1 is omitted - it's free.)
bag(2,44,23,19,96).
bag(3,38,13,14,52).
bag(4,38,15,12,53).
bag(5,35,20,10,95).
bag(6,38,13,13,78).
bag(7,40,26,18,57).
bag(8,50,33,25,79).

% Ordered list of checked bags (after the free carry-on)
bag_list([2,3,4,5,6,7,8]).

% Sum all bag fees
total_bags_fee(Total) :-
    bag_list(L),
    findall(F,
            (nth1(N,L,BagId), bag_fee(BagId,N,F)),
            Fees),
    sumlist(Fees,Total).

% Grand total (ticket + bags)
total_cost(Total) :-
    ticket_price(T),
    total_bags_fee(Bags),
    Total is T + Bags.

% ---------- QUERY ----------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.