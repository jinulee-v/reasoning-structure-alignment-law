/* -------------  RULES (statutes) ------------- */

/* route of the itinerary */
route(europe_us).

/* passenger's service class */
service_class(first_class).

/* price of the ticket */
ticket_price(494).

/* carry-on limits (length, width, height in inches) */
carry_on_limit(22,14,9).

/* ----------  BAG BASE-FEE (1st,2nd,3rd,4th...) FOR EUROPE->US, FIRST CLASS ---------- */
/* 1st-3rd checked bags - free */
base_bag_fee(Index, Fee) :-
    service_class(first_class),
    route(europe_us),
    Index >= 1, Index =< 3,                      % 1st-3rd
    Fee is 0.

/* 4th bag and every bag thereafter - $200 */
base_bag_fee(Index, Fee) :-
    service_class(first_class),
    route(europe_us),
    Index >= 4,                                  % 4th +
    Fee is 200.

/* ----------  OVERSIZE  (sum of dimensions in inches) ---------- */
oversize_fee(SumDim, Fee) :-
    SumDim =< 62,                                % not oversize
    Fee is 0.
oversize_fee(SumDim, Fee) :-
    SumDim > 62, SumDim =< 65,                   % 62-65 in
    Fee is 30.
oversize_fee(SumDim, Fee) :-
    SumDim > 65, SumDim =< 115,                  % 65-115 in
    Fee is 150.

/* ----------  OVERWEIGHT (weight in lbs) ---------- */
overweight_fee(Weight, Fee) :-
    Weight =< 50,                                % =<50 lbs - no fee
    Fee is 0.
overweight_fee(Weight, Fee) :-
    Weight > 50, Weight =< 53,                   % 51-53 lbs
    Fee is 30.
overweight_fee(Weight, Fee) :-
    Weight > 53, Weight =< 70,                   % 54-70 lbs
    Fee is 100.

/* ----------  BAG COST (checked) ---------- */
bag_cost(Index, L,W,H,Weight, Cost) :-
    SumDim is L+W+H,
    oversize_fee(SumDim, OverSize),
    overweight_fee(Weight, OverWeight),
    (OverSize >= OverWeight -> SpecFee = OverSize ; SpecFee = OverWeight),
    base_bag_fee(Index, BaseFee),
    Cost is BaseFee + SpecFee.

/* ----------  BAG LIST (facts from the case) ---------- */
/* bag(Id, Length, Width, Height, Weight) */
bag(b1, 21, 13,  8, 10).   % backpack - carry-on
bag(b2, 45, 30, 20, 51).   % backpack - checked
bag(b3, 38, 12, 14, 51).   % luggage box - checked
bag(b4, 38, 11, 14, 53).   % backpack - checked
bag(b5, 38, 24, 16, 66).   % luggage box - checked

/* ----------  CARRY-ON? ---------- */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_limit(LC,WC,HC),
    L =< LC, W =< WC, H =< HC.

/* ----------  COLLECT CHECKED BAGS WITH POSITION NUMBER ---------- */
checked_bag_with_index(Index, Id, L,W,H,Weight) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), BagList),
    nth1(Index, BagList, Id),
    bag(Id,L,W,H,Weight).

/* ----------  TOTAL BAG FEES ---------- */
total_checked_bags_cost(Total) :-
    findall(Cost,
        (checked_bag_with_index(I, _Id, L,W,H,Weight),
         bag_cost(I,L,W,H,Weight,Cost)),
        Costs),
    sum_list(Costs, Total).

/* ----------  TOTAL COST (ticket + bags) ---------- */
total_cost(Total) :-
    ticket_price(Ticket),
    total_checked_bags_cost(BagFees),
    Total is Ticket + BagFees.

/* -------------  QUERY ------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.