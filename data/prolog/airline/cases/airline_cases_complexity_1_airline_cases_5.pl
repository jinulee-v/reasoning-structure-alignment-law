/* ---------------  General rules coming from the statutes --------------- */

/* Base fee for each successive checked bag on a Premium Economy ticket
   for travel wholly within the U.S. (Austin - San Francisco)            */
base_fee(1,0).
base_fee(2,0).
base_fee(3,150).
base_fee(N,200):- N>=4.

/* ---------------- Over-WEIGHT surcharge (within U.S.) ------------------ */
overweight_surcharge(Weight,Fee):-               % =< 50 lb - no surcharge
    Weight =< 50,             Fee is 0.
overweight_surcharge(Weight,30):-                % 50  < W =< 53 lb - $30
    Weight  > 50,  Weight =< 53.
overweight_surcharge(Weight,100):-               % 53  < W =< 70 lb - $100
    Weight  > 53,  Weight =< 70.
overweight_surcharge(Weight,200):-               % 70  < W =<100 lb - $200
    Weight  > 70,  Weight =< 100.

/* ---------------- Over-SIZE surcharge (within U.S.) -------------------- */
oversize_surcharge(DimSum,0):-                   % =< 62 in  - no surcharge
    DimSum =< 62.
oversize_surcharge(DimSum,30):-                  % 62 < D =< 65 in - $30
    DimSum  > 62, DimSum =< 65.
oversize_surcharge(DimSum,200):-                 % 65 < D =<115 in - $200
    DimSum  > 65, DimSum =< 115.

/* --------------  For a given bag, determine its surcharge -------------- */
bag_surcharge(Weight,DimSum,Surcharge):-
    overweight_surcharge(Weight,OW),
    oversize_surcharge(DimSum,OS),
    Surcharge is max(OW,OS).

/* -----------------  Cost of an individual checked bag ------------------ */
bag_cost(Order,Weight,DimSum,Cost):-
    base_fee(Order,Base),
    bag_surcharge(Weight,DimSum,Surcharge),
    Cost is Base + Surcharge.

/* -----------------------------  Facts  --------------------------------- */

/* Carry-on (meets 22*14*9, no fee, omitted from cost calculation) */
carry_on(1).

/* Checked bags:  id,  L,  W,  H,  Weight (lb) */
bag_data(2,35,19, 9, 54).
bag_data(3,35,21, 9, 89).
bag_data(4,37,13,14, 73).
bag_data(5,51,28,29, 70).
bag_data(6,45,27,20, 97).
bag_data(7,35,17,12, 58).
bag_data(8,36,17,10, 57).

/* List of checked-bag IDs in the order they are presented */
bag_ids([2,3,4,5,6,7,8]).

/* --------------------  Summation utilities  ---------------------------- */
sumlist([],0).
sumlist([H|T],S):- sumlist(T,S1), S is H+S1.

/* --------------------  Compute total bag fees  ------------------------- */
bag_costs([],_,[]).
bag_costs([Id|Rest],Idx,[Cost|Cs]):-
    bag_data(Id,L,W,H,Weight),
    DimSum is L+W+H,
    bag_cost(Idx,Weight,DimSum,Cost),
    Idx1 is Idx+1,
    bag_costs(Rest,Idx1,Cs).

bag_total(Total):-
    bag_ids(Ids),
    bag_costs(Ids,1,CostList),
    sumlist(CostList,Total).

/* ----------------------  Flight ticket price  -------------------------- */
flight_cost(157).

/* -------------------------  Grand total  ------------------------------- */
total_cost(Total):-
    bag_total(Bags),
    flight_cost(Flight),
    Total is Bags + Flight.

/* ---------------------  Produce the answer  ---------------------------- */
:- total_cost(T), format('Total cost: ~w~n', [T]).
:- halt.