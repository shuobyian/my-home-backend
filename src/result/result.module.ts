import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { MarketModule } from 'src/market/market.module';
import { MaterialModule } from 'src/material/material.module';
import { ProductModule } from 'src/product/product.module';
import { Result } from 'src/result/entities/result.entity';
import { ResultController } from 'src/result/result.controller';
import { ResultService } from 'src/result/result.service';

@Module({
  imports: [
    TypeOrmModule.forFeature([Result]),
    forwardRef(() => ProductModule),
    forwardRef(() => MaterialModule),
    forwardRef(() => MarketModule),
  ],
  controllers: [ResultController],
  providers: [ResultService],
  exports: [ResultService],
})
export class ResultModule {}
