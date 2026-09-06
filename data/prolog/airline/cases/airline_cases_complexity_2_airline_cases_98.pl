/* ---------- Facts describing William's flight -------------------- */
flight_route(south_america_to_us).   /* Lima (Peru)  -> Orlando (U.S.)   */
flight_class(first).                 /* First Class ticket               */
flight_ticket_cost(293).

/* ---------- Bags (only the checked ones, carry-on omitted) --------
      bag(ID, Weight_lbs, Size_inches_sum).                           */
bag(b2,  51,  89).
bag(b3,  97,  64).
bag(b4,  53,  82).
bag(b5,  87,  87).
bag(b6,  69,  63).
bag(b7,  93,  68).
bag(b8,  51, 100).
bag(b9,  65,  65).
bag(b10, 52,  63).
bag(b11, 95, 107).

bags([b2,b3,b4,b5,b6,b7,b8,b9,b10,b11]).   /* convenience list       */

/* ---------- Baseline checked-bag fee (Fourth bag and on) ----------- */
baseline_free(free,    0).
baseline_free(charged, 200).

/* ---------- Oversize fees (South America -> U.S. table) ------------ */
oversize_fee(Size, 0   ) :- Size =< 62.
oversize_fee(Size, 30  ) :- Size  > 62, Size =< 65.      /* 62-65 in */
oversize_fee(Size, 150 ) :- Size  > 65, Size =< 115.     /* 65-115 in */

/* ---------- Over-weight fees (South America -> U.S.) --------------- */
/* First 3 bags: 70 lb allowance, all others: 50 lb allowance.         */
overweight_fee(free,    W, 200) :- W >  70, W =< 100.
overweight_fee(free,    W, 0  )  :- W =< 70.

overweight_fee(charged, W, 200) :- W > 70,  W =< 100.
overweight_fee(charged, W, 100) :- W > 53,  W =< 70.
overweight_fee(charged, W, 30 ) :- W > 50,  W =< 53.
overweight_fee(charged, W, 0  ) :- W =< 50.

/* ---------- Cost of a single bag ---------------------------------- */
bag_cost(BagID, Status, Cost) :-
    bag(BagID, Weight, Size),
    baseline_free(Status, Base),
    oversize_fee(Size,  OSFee),
    overweight_fee(Status, Weight, OWFee),
    MaxFee is max(OSFee, OWFee),
    Cost   is Base + MaxFee.

/* ---------- Choose any 3 bags to be the free ones ------------------ */
choose_free(List, [A,B,C]) :-
    select(A,List,R1),
    select(B,R1,R2),  A @< B,    /* keep combinations unique */
    select(C,R2,_),   B @< C.

/* ---------- Total cost of bags for a given choice of free bags ----- */
bags_total_cost(FreeList, Total) :-
    bags(All),
    bags_total_cost(All, FreeList, 0, Total).

bags_total_cost([], _, Tot, Tot).
bags_total_cost([Bag|Rest], FreeList, Acc, Tot) :-
    ( member(Bag,FreeList) -> Status = free ; Status = charged ),
    bag_cost(Bag, Status, BagCost),
    Acc1 is Acc + BagCost,
    bags_total_cost(Rest, FreeList, Acc1, Tot).

/* ---------- Minimise over all possible choices of free bags -------- */
min_bag_cost(MinCost) :-
    bags(BagIDs),
    findall(Cost,
            ( choose_free(BagIDs,Free3),
              bags_total_cost(Free3,Cost)
            ),
            Costs),
    min_list(Costs, MinCost).

/* ---------- Final total (bags + ticket) ---------------------------- */
total_cost(Total) :-
    min_bag_cost(BagsCost),
    flight_ticket_cost(Ticket),
    Total is BagsCost + Ticket.

/* ---------- Query to print the answer ------------------------------ */
:- total_cost(Total),
   format('Total cost: ~w~n', [Total]),
   halt.